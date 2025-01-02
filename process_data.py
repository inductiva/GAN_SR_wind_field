"""
process_data.py
Written by Jacob Wulff Wold 2023
Apache License

Downloads, preprocesses and saves the data. Creates customized dataloaders with data augmentation functionality.
"""

import torch
import numpy as np
import torch.nn.parallel
import torch.utils.data
import pickle
from download_data import (
    download_and_split,
    slice_only_dim_dicts,
    slice_dict_folder_name,
    get_interpolated_z_data,
    get_static_data,
    filenames_from_start_and_end_dates,
    download_all_files,
    prepare_and_split,
)
from datetime import date
import os


class CustomizedDataset(torch.utils.data.Dataset):
    def __init__(
        self,
        filenames,
        subfolder_name,
        Z_MIN,
        Z_MAX,
        UVW_MAX,
        P_MIN,
        P_MAX,
        Z_ABOVE_GROUND_MAX,
        x,
        y,
        terrain,
        include_pressure=False,
        include_z_channel=False,
        interpolate_z=False,
        include_above_ground_channel=False,
        COARSENESS_FACTOR=4,
        data_aug_rot=True,
        data_aug_flip=True,
        enable_slicing=False,
        slice_size=64,
        for_plotting=False,
        is_test=False,
    ):
        self.subfolder_name = subfolder_name
        self.include_pressure = include_pressure
        self.include_z_channel = include_z_channel
        self.interpolate_z = interpolate_z
        self.include_above_ground_channel = include_above_ground_channel
        self.coarseness_factor = COARSENESS_FACTOR
        self.Z_MIN = Z_MIN
        self.Z_MAX = Z_MAX
        self.Z_ABOVE_GROUND_MAX = Z_ABOVE_GROUND_MAX
        self.UVW_MAX = UVW_MAX
        self.P_MIN = P_MIN
        self.P_MAX = P_MAX
        self.x = x
        self.y = y
        self.data_aug_rot = data_aug_rot
        self.data_aug_flip = data_aug_flip
        self.terrain = terrain
        self.enable_slicing = enable_slicing
        self.slice_size = slice_size
        self.for_plotting = for_plotting
        self.is_test = is_test
        self.slice_index = 0
        self.filenames = filenames

        if not os.path.exists(
            "./data/full_dataset_files/" + self.subfolder_name + "/max/"
        ):
            os.makedirs("./data/full_dataset_files/" + self.subfolder_name + "/max/")
        if not os.path.exists("./data/interpolated_z_data/" + self.subfolder_name):
            os.makedirs("./data/interpolated_z_data/" + self.subfolder_name)

        if not os.path.isfile(
            "./data/full_dataset_files/"
            + self.subfolder_name
            + "/"
            + "norm_factors.pkl"
        ):
            pickle.dump(
                [
                    Z_MIN,
                    Z_MAX,
                    Z_ABOVE_GROUND_MAX,
                    UVW_MAX,
                    P_MIN,
                    P_MAX,
                ],
                open(
                    "./data/full_dataset_files/"
                    + self.subfolder_name
                    + "/"
                    + "norm_factors.pkl",
                    "wb",
                ),
            )

    def __len__(self):
        "Denotes the total number of samples"
        return len(self.filenames)

    def __getitem__(self, index):
        "Generates one sample of data"
        # Select sample
        z, z_above_ground, u, v, w, pressure = pickle.load(
            open(
                "./data/full_dataset_files/"
                + self.subfolder_name
                + self.filenames[index],
                "rb",
            )
        )

        if self.interpolate_z:
            if self.is_test:
                LR_raw, HR_raw, Z_raw = reformat_to_torch(
                    u,
                    v,
                    w,
                    pressure,
                    z,
                    z_above_ground,
                    self.Z_MIN,
                    self.Z_MAX,
                    self.Z_ABOVE_GROUND_MAX,
                    self.UVW_MAX,
                    self.P_MIN,
                    self.P_MAX,
                    coarseness_factor=self.coarseness_factor,
                    include_pressure=self.include_pressure,
                    include_z_channel=self.include_z_channel,
                    include_above_ground_channel=self.include_above_ground_channel,
                    for_plotting=self.for_plotting,
                )

            z, z_above_ground, u, v, w, pressure = get_interpolated_z_data(
                "./data/interpolated_z_data/"
                + self.subfolder_name
                + self.filenames[index],
                self.x,
                self.y,
                z_above_ground,
                u,
                v,
                w,
                pressure,
                self.terrain,
            )

        if self.enable_slicing:
            x_start = round(
                np.random.beta(0.25, 0.25) * (self.x.size - self.slice_size)
            )
            y_start = round(
                np.random.beta(0.25, 0.25) * (self.y.size - self.slice_size)
            )
            z, z_above_ground, u, v, w, pressure = slice_only_dim_dicts(
                z,
                z_above_ground,
                u,
                v,
                w,
                pressure,
                x_dict={"start": x_start, "max": x_start + self.slice_size, "step": 1},
                y_dict={"start": y_start, "max": y_start + self.slice_size, "step": 1},
                z_dict={"start": 0, "max": z.shape[-1], "step": 1},
            )

        LR, HR, Z = reformat_to_torch(
            u,
            v,
            w,
            pressure,
            z,
            z_above_ground,
            self.Z_MIN,
            self.Z_MAX,
            self.Z_ABOVE_GROUND_MAX,
            self.UVW_MAX,
            self.P_MIN,
            self.P_MAX,
            coarseness_factor=self.coarseness_factor,
            include_pressure=self.include_pressure,
            include_z_channel=self.include_z_channel,
            include_above_ground_channel=self.include_above_ground_channel,
            for_plotting=self.for_plotting,
        )

        if self.data_aug_rot:
            amount_of_rotations = np.random.randint(0, 4)
            LR = torch.rot90(LR, amount_of_rotations, [1, 2])
            HR = torch.rot90(HR, amount_of_rotations, [1, 2])
            Z = torch.rot90(Z, amount_of_rotations, [1, 2])

            if amount_of_rotations == 1:
                HR[:2] = torch.concatenate(
                    (
                        -torch.index_select(HR, 0, torch.tensor(1)),
                        torch.index_select(HR, 0, torch.tensor(0)),
                    ),
                    0,
                )
                LR[:2] = torch.concatenate(
                    (
                        -torch.index_select(LR, 0, torch.tensor(1)),
                        torch.index_select(LR, 0, torch.tensor(0)),
                    ),
                    0,
                )
            if amount_of_rotations == 2:
                HR[:2] = torch.concatenate(
                    (
                        -torch.index_select(HR, 0, torch.tensor(0)),
                        -torch.index_select(HR, 0, torch.tensor(1)),
                    ),
                    0,
                )
                LR[:2] = torch.concatenate(
                    (
                        -torch.index_select(LR, 0, torch.tensor(0)),
                        -torch.index_select(LR, 0, torch.tensor(1)),
                    ),
                    0,
                )
            if amount_of_rotations == 3:
                HR[:2] = torch.concatenate(
                    (
                        torch.index_select(HR, 0, torch.tensor(1)),
                        -torch.index_select(HR, 0, torch.tensor(0)),
                    ),
                    0,
                )
                LR[:2] = torch.concatenate(
                    (
                        torch.index_select(LR, 0, torch.tensor(1)),
                        -torch.index_select(LR, 0, torch.tensor(0)),
                    ),
                    0,
                )

        if self.data_aug_flip:
            if np.random.rand() > 0.5:
                LR = torch.flip(LR, [1])
                HR = torch.flip(HR, [1])
                Z = torch.flip(Z, [1])
                LR[0] = -LR[0]
                HR[0] = -HR[0]
            if np.random.rand() > 0.5:
                LR = torch.flip(LR, [2])
                HR = torch.flip(HR, [2])
                Z = torch.flip(Z, [2])
                LR[1] = -LR[1]
                HR[1] = -HR[1]

        if self.is_test:
            if self.interpolate_z:
                return LR, HR, Z, self.filenames[index][:-4], HR_raw, Z_raw
            else:
                return LR, HR, Z, self.filenames[index][:-4], 0, 0

        return LR, HR, Z


def calculate_div_z(HR_data: torch.Tensor, Z: torch.Tensor):
    dZ = torch.tile(
        Z[:, :, :, :, 1:] - Z[:, :, :, :, :-1], [1, HR_data.shape[1], 1, 1, 1]
    )

    derivatives = torch.zeros_like(HR_data)

    derivatives[:, :, :, :, 1:-1] = (
        dZ[:, :, :, :, :-1] ** 2 * HR_data[:, :, :, :, 2:]
        + (dZ[:, :, :, :, 1:] ** 2 - dZ[:, :, :, :, :-1] ** 2)
        * HR_data[:, :, :, :, 1:-1]
        - dZ[:, :, :, :, 1:] ** 2 * HR_data[:, :, :, :, :-2]
    ) / (
        dZ[:, :, :, :, :-1]
        * dZ[:, :, :, :, 1:]
        * (dZ[:, :, :, :, :-1] + dZ[:, :, :, :, 1:])
    )

    derivatives[:, :, :, :, -1] = (
        HR_data[:, :, :, :, -1] - HR_data[:, :, :, :, -2]
    ) / dZ[:, :, :, :, -1]
    derivatives[:, :, :, :, 0] = (HR_data[:, :, :, :, 1] - HR_data[:, :, :, :, 0]) / dZ[
        :, :, :, :, 0
    ]

    return derivatives


@torch.jit.script
def calculate_gradient_of_wind_field(HR_data, x, y, Z):
    grad_x, grad_y = torch.gradient(HR_data, dim=(2, 3), spacing=(x, y))
    grad_z = calculate_div_z(HR_data, Z)

    return torch.cat(
        (
            grad_x,
            grad_y,
            grad_z,
        ),
        dim=1,
    )

def prepare_data(
    start_date: date,
    end_date: date,
    x_dict,
    y_dict,
    z_dict,
    terrain,
    folder,
    destination_folder,
    train_eval_test_ratio=0.8,
):
    filenames = filenames_from_start_and_end_dates(start_date, end_date)
    Z_MIN, Z_MAX, UVW_MAX, P_MIN, P_MAX, Z_ABOVE_GROUND_MAX = 10000, 0, 0, 1000000, 0, 0

    finished = False
    start = -1
    subfolder = slice_dict_folder_name(x_dict, y_dict, z_dict)

    if not os.path.exists(folder + subfolder):
        os.makedirs(folder + subfolder + "/max/")

    invalid_samples = set()
    while not finished:
        for i in range(len(filenames)):
            if filenames[i] not in invalid_samples:
                try:
                    with open(
                        folder + subfolder + "max/max_" + filenames[i], "rb"
                    ) as f:
                        (
                            z_min,
                            z_max,
                            z_above_ground_max,
                            uvw_max,
                            p_min,
                            p_max,
                        ) = pickle.load(f)
                    if i < train_eval_test_ratio * len(filenames):
                        Z_MIN = min(Z_MIN, z_min)
                        Z_MAX = max(Z_MAX, z_max)
                        UVW_MAX = max(UVW_MAX, uvw_max)
                        P_MIN = min(P_MIN, p_min)
                        P_MAX = max(P_MAX, p_max)
                        Z_ABOVE_GROUND_MAX = max(Z_ABOVE_GROUND_MAX, z_above_ground_max)

                    if start != -1:
                        print(
                            "Spliting and processing data, from ",
                            filenames[start],
                            " to ",
                            filenames[i],
                        )
                        invalid_samples = invalid_samples.union(
                            prepare_and_split(
                                filenames[start:i],
                                terrain,
                                x_dict,
                                y_dict,
                                z_dict,
                                destination_folder,
                                folder=folder + subfolder,
                            )
                        )
                        start = -1
                except FileNotFoundError:
                    if start == -1:
                        start = i

            if i == len(filenames) - 1:
                if start != -1:
                    print(
                        "Spliting and processing data, from  ",
                        filenames[start],
                        " to ",
                        filenames[i],
                    )
                    invalid_samples = invalid_samples.union(
                        prepare_and_split(
                            filenames[start:],
                            terrain,
                            x_dict,
                            y_dict,
                            z_dict,
                            destination_folder,
                            folder=folder + subfolder,
                        )
                    )
                    start = -1
                else:
                    finished = True

    filenames = [item for item in filenames if item not in invalid_samples]

    print("Data processed successfully")
    return filenames, subfolder, Z_MIN, Z_MAX, Z_ABOVE_GROUND_MAX, UVW_MAX, P_MIN, P_MAX

def download_all_files_and_prepare(
    start_date: date,
    end_date: date,
    x_dict,
    y_dict,
    z_dict,
    terrain,
    folder: str = "./data/full_dataset_files/",
    train_eval_test_ratio=0.8,
):
    filenames = filenames_from_start_and_end_dates(start_date, end_date)
    Z_MIN, Z_MAX, UVW_MAX, P_MIN, P_MAX, Z_ABOVE_GROUND_MAX = 10000, 0, 0, 1000000, 0, 0

    finished = False
    start = -1
    subfolder = slice_dict_folder_name(x_dict, y_dict, z_dict)
    if os.path.exists("./data/downloaded_raw_bessaker_data/invalid_files.txt"):
        invalid_urls = set(
            line.strip()
            for line in open("./data/downloaded_raw_bessaker_data/invalid_files.txt")
        )
    else:
        invalid_urls = set()

    if not os.path.exists(folder + subfolder):
        os.makedirs(folder + subfolder + "/max/")

    invalid_samples = set()

    while not finished:
        for i in range(len(filenames)):
            if filenames[i] not in invalid_samples:
                try:
                    with open(
                        folder + subfolder + "max/max_" + filenames[i], "rb"
                    ) as f:
                        (
                            z_min,
                            z_max,
                            z_above_ground_max,
                            uvw_max,
                            p_min,
                            p_max,
                        ) = pickle.load(f)
                    if i < train_eval_test_ratio * len(filenames):
                        Z_MIN = min(Z_MIN, z_min)
                        Z_MAX = max(Z_MAX, z_max)
                        UVW_MAX = max(UVW_MAX, uvw_max)
                        P_MIN = min(P_MIN, p_min)
                        P_MAX = max(P_MAX, p_max)
                        Z_ABOVE_GROUND_MAX = max(Z_ABOVE_GROUND_MAX, z_above_ground_max)

                    if start != -1:
                        print(
                            "Downloading new files, from ",
                            filenames[start],
                            " to ",
                            filenames[i],
                        )
                        invalid_samples = invalid_samples.union(
                            download_and_split(
                                filenames[start:i],
                                terrain,
                                x_dict,
                                y_dict,
                                z_dict,
                                invalid_urls,
                                folder=folder + subfolder,
                            )
                        )
                        start = -1
                except FileNotFoundError:
                    if start == -1:
                        start = i

            if i == len(filenames) - 1:
                if start != -1:
                    print(
                        "Downloading new files, from ",
                        filenames[start],
                        " to ",
                        filenames[i],
                    )
                    invalid_samples = invalid_samples.union(
                        download_and_split(
                            filenames[start:],
                            terrain,
                            x_dict,
                            y_dict,
                            z_dict,
                            invalid_urls,
                            folder=folder + subfolder,
                        )
                    )
                    start = -1
                else:
                    finished = True

    filenames = [item for item in filenames if item not in invalid_samples]

    print("Finished downloading all files")
    return filenames, subfolder, Z_MIN, Z_MAX, Z_ABOVE_GROUND_MAX, UVW_MAX, P_MIN, P_MAX


def reformat_to_torch(
    u,
    v,
    w,
    p,
    z,
    z_above_ground,
    Z_MIN,
    Z_MAX,
    Z_ABOVE_GROUND_MAX,
    UVW_MAX,
    P_MIN,
    P_MAX,
    coarseness_factor=4,
    include_pressure=False,
    include_z_channel=False,
    include_above_ground_channel=False,
    for_plotting=False,
):
    HR_arr = (
        np.concatenate(
            (u[np.newaxis, :, :, :], v[np.newaxis, :, :, :], w[np.newaxis, :, :, :]),
            axis=0,
        )
        / UVW_MAX
    )
    del u, v, w

    if include_pressure:
        arr_norm_LR = np.concatenate(
            (HR_arr, (p[np.newaxis, :, :, :] - P_MIN) / (P_MAX - P_MIN)), axis=0
        )[:, ::coarseness_factor, ::coarseness_factor, :]
        if for_plotting:
            HR_arr = np.concatenate(
                (HR_arr, (p[np.newaxis, :, :, :] - P_MIN) / (P_MAX - P_MIN)), axis=0
            )
    else:
        arr_norm_LR = HR_arr[:, ::coarseness_factor, ::coarseness_factor, :]

    if include_z_channel:
        if include_above_ground_channel:
            arr_norm_LR = np.concatenate(
                (
                    arr_norm_LR,
                    z_above_ground[
                        np.newaxis, ::coarseness_factor, ::coarseness_factor, :
                    ]
                    / Z_ABOVE_GROUND_MAX,
                    (z - z_above_ground - Z_MIN)[
                        np.newaxis, ::coarseness_factor, ::coarseness_factor, :
                    ]
                    / (Z_MAX - Z_MIN - Z_ABOVE_GROUND_MAX),
                ),
                axis=0,
            )
            del z_above_ground
        else:
            arr_norm_LR = np.concatenate(
                (
                    arr_norm_LR,
                    (z[np.newaxis, ::coarseness_factor, ::coarseness_factor, :] - Z_MIN)
                    / (Z_MAX - Z_MIN),
                ),
                axis=0,
            )

    HR_data = torch.from_numpy(HR_arr).float()
    LR_data = torch.from_numpy(arr_norm_LR).float()
    z = torch.from_numpy(z[np.newaxis, :, :, :]).float()

    return (
        LR_data,
        HR_data,
        z,
    )


def preprosess(
    train_eval_test_ratio=0.8,
    X_DICT={"start": 0, "max": 128, "step": 1},
    Y_DICT={"start": 0, "max": 128, "step": 1},
    Z_DICT={"start": 0, "max": 10, "step": 1},
    start_date=date(2018, 4, 1),
    end_date=date(2018, 4, 3),
    include_pressure=True,
    include_z_channel=False,
    interpolate_z=False,
    enable_slicing=False,
    slice_size=64,
    include_above_ground_channel=False,
    COARSENESS_FACTOR=4,
    train_aug_rot=False,
    val_aug_rot=False,
    train_aug_flip=False,
    val_aug_flip=False,
    for_plotting=False,
    isDownload=False,
):
    #First check if --download flag is set, if True then download all files,
    # else extract terrain data from downloaded data
    processed_data_folder="./data/full_dataset_files/"
    destination_folder="./data/downloaded_raw_bessaker_data/"

    if isDownload:
        download_all_files(start_date, 
                           end_date,
                           destination_folder,)
    if not os.path.exists(os.path.join(processed_data_folder,"static_terrain_x_y.pkl")):
        get_static_data(destination_folder, processed_data_folder)
    with open(os.path.join(processed_data_folder,"static_terrain_x_y.pkl"), "rb") as f:
            terrain, x, y = slice_only_dim_dicts(
                *pickle.load(f), x_dict=X_DICT, y_dict=Y_DICT
                )

    (
        filenames,
        subfolder,
        Z_MIN,
        Z_MAX,
        Z_ABOVE_GROUND_MAX,
        UVW_MAX,
        P_MIN,
        P_MAX,
    ) = prepare_data(
        start_date,
        end_date,
        X_DICT,
        Y_DICT,
        Z_DICT,
        terrain,
        processed_data_folder,
        destination_folder,
        train_eval_test_ratio=train_eval_test_ratio,
    )
    number_of_train_samples = int(len(filenames) * train_eval_test_ratio)
    number_of_test_samples = int(len(filenames) * (1 - train_eval_test_ratio) / 2)

    dataset_train = CustomizedDataset(
        filenames[:number_of_train_samples],
        subfolder,
        Z_MIN,
        Z_MAX,
        UVW_MAX,
        P_MIN,
        P_MAX,
        Z_ABOVE_GROUND_MAX,
        x,
        y,
        terrain,
        include_pressure=include_pressure,
        include_z_channel=include_z_channel,
        interpolate_z=interpolate_z,
        include_above_ground_channel=include_above_ground_channel,
        COARSENESS_FACTOR=COARSENESS_FACTOR,
        data_aug_rot=train_aug_rot,
        data_aug_flip=train_aug_flip,
        enable_slicing=enable_slicing,
        slice_size=slice_size,
        for_plotting=for_plotting,
    )

    dataset_test = CustomizedDataset(
        filenames[
            number_of_train_samples : number_of_train_samples + number_of_test_samples
        ],
        subfolder,
        Z_MIN,
        Z_MAX,
        UVW_MAX,
        P_MIN,
        P_MAX,
        Z_ABOVE_GROUND_MAX,
        x,
        y,
        terrain,
        include_pressure=include_pressure,
        include_z_channel=include_z_channel,
        interpolate_z=interpolate_z,
        include_above_ground_channel=include_above_ground_channel,
        COARSENESS_FACTOR=COARSENESS_FACTOR,
        data_aug_rot=False,
        data_aug_flip=False,
        enable_slicing=False,
        slice_size=slice_size,
        is_test=True,
    )

    dataset_validation = CustomizedDataset(
        filenames[number_of_train_samples + number_of_test_samples :],
        subfolder,
        Z_MIN,
        Z_MAX,
        UVW_MAX,
        P_MIN,
        P_MAX,
        Z_ABOVE_GROUND_MAX,
        x,
        y,
        terrain,
        include_pressure=include_pressure,
        include_z_channel=include_z_channel,
        interpolate_z=interpolate_z,
        include_above_ground_channel=include_above_ground_channel,
        COARSENESS_FACTOR=COARSENESS_FACTOR,
        data_aug_rot=val_aug_rot,
        data_aug_flip=val_aug_flip,
        enable_slicing=enable_slicing,
        slice_size=slice_size,
    )

    if enable_slicing:  # regular spacing so values are irrelevant
        (
            x,
            y,
        ) = (
            x[:slice_size],
            y[:slice_size],
        )

    return (
        dataset_train,
        dataset_test,
        dataset_validation,
        torch.from_numpy(x).float(),
        torch.from_numpy(y).float(),
    )


if __name__ == "__main__":
    preprosess(include_above_ground_channel=True)

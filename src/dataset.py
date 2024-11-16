import json
import os
from enum import Enum
from PIL import Image

import cv2
import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader
from tqdm import tqdm

from lavis.processors.blip_processors import (
    BlipCaptionProcessor,
    BlipImageEvalProcessor,
    Blip2ImageTrainProcessor
)


FACEFORENSINCS_PATH = "/media/vhondru/hdd/dp/manipulated_videos"
DEEPFAKECHALLENGE_PATH = "/media/vhondru/hdd/deepfake_dataset_challenge"


class Label(Enum):
    REAL = 0.0
    FAKE = 1.0
INPUT_NO_OF_FRAMES = 5
WIDTH = 500
HEIGHT = 400

class ExplainableDataset(Dataset):
    def __init__(self, split, vis_processors=None) -> None:
        csv_data_fake = pd.read_csv("/home/vhondru/vhondru/phd/biodeep/xAI_deepfake/dataset.csv")
        csv_data_fake["movie_name"] = csv_data_fake.apply(self._obtain_path, axis=1)
        csv_data_fake["label"] = Label.FAKE.value

        # csv_data_real = csv_data_fake.copy()
        # csv_data_real["movie_name"] = csv_data_real["movie_name"].map(
        #     lambda x: os.path.join("/media/vhondru/hdd/dp/original_data/original/data/original_sequences/youtube/c23/videos", x)
        # )
        # csv_data_real["text"] = "There is nothing unnormal in the video."
        # csv_data_real["label"] = Label.REAL.value

        # self.csv_data = pd.concat((csv_data_fake, csv_data_real))
        self.csv_data = csv_data_fake


        self.csv_data = self.csv_data.sample(frac=1, random_state=0).reset_index()

        if split == "train":
            self.csv_data = self.csv_data[100:]
        elif split == "val":
            self.csv_data = self.csv_data[:100]
        else:
            raise Exception(f"split={split} not implemented.")

        self.csv_data.reset_index(inplace=True)

        self.vis_processor = vis_processors
        self.text_processor = BlipCaptionProcessor()

        self.counter = 0
        self.users = {"Vlad Hondru": 0, "Eduard Hogea": 0}

    def get_img_ids(self):
        return self.csv_data["id"].to_list()

    def _obtain_path(self, row):
        if row["dataset"] == "Farceforensics++":
            return os.path.join(FACEFORENSINCS_PATH, row["manipulation"], row["movie_name"])
        elif row["dataset"] == "DeepfakeDetection":
            return os.path.join(DEEPFAKECHALLENGE_PATH, row["manipulation"], row["movie_name"])

    def __len__(self):
        return len(self.csv_data)
    
    def collater(self, samples):
        # Filter out None samples
        samples = [s for s in samples if s is not None]
        # Check if samples is empty after filtering
        if not samples:
            return {}
        collated_dict = {}
        keys = samples[0].keys() # Use the keys of the first sample as a reference
        for k in keys:
            values = [sample[k] for sample in samples]
            # If the value type for the key is torch.Tensor, stack them else return list
            collated_dict[k] = torch.stack(values, dim=0) if isinstance(values[0], torch.Tensor) else values

        return collated_dict
        # return default_collate(samples)
    
    def __getitem__(self, index):
        video_metadata = self.csv_data.loc[index]

        movie_name = video_metadata["movie_name"]
        text = video_metadata["text"]
        click_locations = video_metadata["click_locations"]
        label = video_metadata["label"]
        image_id = video_metadata["id"]

        cap = cv2.VideoCapture(movie_name)
        movie_no_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        frames_indices = np.linspace(start=0, stop=movie_no_frames-1, num=INPUT_NO_OF_FRAMES)
        frames_indices = frames_indices.astype(int)

        # Use frames on clicked locations if they exist
        # if click_locations != "{}":
        #     click_locations = json.loads(click_locations)

        #     frames_with_click = list(click_locations.keys())
        #     frames_with_click = list(map(int, frames_with_click))
        #     frames_with_click.sort()

        #     # Debug
        #     # max_frame_no = max(frames_with_click)
        #     # if max_frame_no > movie_no_frames:
        #     #     self.counter += 1
        #     #     self.users[video_metadata["username"]] += 1

        #     i = 0
        #     while len(frames_indices) - len(frames_with_click) > 0:
        #         if i % 2 == 0 and frames_indices[-i-1] not in frames_with_click:
        #             frames_with_click.append(frames_indices[-i-1])
        #         elif i % 2 != 0 and frames_indices[i] not in frames_with_click:
        #             frames_with_click.append(frames_indices[i])

        #         i = i + 1

        #     frames_indices = sorted(frames_with_click)

        #     frames_indices = list(map(int, frames_indices))

        frames = []
        for frame_ind in frames_indices[:INPUT_NO_OF_FRAMES]:
            if frame_ind == movie_no_frames:
                frame_ind = frame_ind - 1

            # Set the current frame position to the desired frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_ind)

            # Read the frame
            ret, frame = cap.read()

            # frame = cv2.resize(frame, (WIDTH, HEIGHT))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = Image.fromarray(frame)
            frame = self.vis_processor(frame)

            frames.append(frame)

        # Read attention map
        att_map_path = movie_name.replace(video_metadata["manipulation"], f"attention_maps_{video_metadata['manipulation']}2")
        att_map_path = att_map_path.replace(att_map_path[-3:], "png")
        attention_map = np.array(Image.open(att_map_path)) / 255.0

        text_input = self.text_processor(text)
    
        return {
            "image": torch.stack(frames),
            "label": torch.tensor(label),
            "text_input": text_input,
            "image_id": image_id, 
            "attention_map": torch.tensor(attention_map),
        }


if __name__ == "__main__":
    """
    ds = ExplainableDataset("train", Blip2ImageTrainProcessor())
    # ds = ExplainableDataset("val", BlipImageEvalProcessor(image_size=364)),

    dl = DataLoader(ds, batch_size=8, shuffle=True, num_workers=0, pin_memory=True)

    for batch in tqdm(dl):
        continue

    print(ds.counter)
    print(ds.users)
    """

    # ds = ExplainableDataset("train", Blip2ImageTrainProcessor())
    ds2 = ExplainableDataset("val", BlipImageEvalProcessor(image_size=364))

    dl2 = DataLoader(ds2, batch_size=8, shuffle=True, num_workers=0, pin_memory=True, collate_fn=ds2.collater)

    for batch in tqdm(dl2):
        continue

    print(ds2.counter)
    print(ds2.users)

    #     frames = batch["image"].to(device="cuda")
    #     labels = batch["label"].to(device="cuda")
    #     text_input = batch["text_input"]#.to(device="cuda")

    #     # frames = torch.permute(frames, (0,1,4,2,3))

    #     print(frames.shape)
    #     print(labels)
    #     print(text_input)

    #     break

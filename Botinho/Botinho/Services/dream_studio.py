import io
import argparse
import tempfile

import requests
from PIL import Image

from stability_sdk import client
import stability_sdk.interfaces.gooseai.generation.generation_pb2 as generation

from config import Settings, get_settings
settings: Settings = get_settings()

MULT = 64
MAX_SIZE = 1024, 1024


def retrieve_image_from_url(uri: str, max_size: tuple = None) -> Image:
    with tempfile.SpooledTemporaryFile() as buffer:
        r = requests.get(uri, stream=True)

        if max_size is None:
            max_size = MAX_SIZE

        if r.status_code == 200:
            for chunk in r.iter_content(chunk_size=1024):
                buffer.write(chunk)

            buffer.seek(0)

            img = Image.open(io.BytesIO(buffer.read()))
            img.thumbnail(max_size, Image.Resampling.LANCZOS)

            width, height = img.size

            return img.crop((0, 0, width - (width % MULT), height - (height % MULT)))


class ImageGenerator:
    def __init__(self):
        self.conn = self.connection()

    @staticmethod
    def connection():
        return client.StabilityInference(
            key=settings.dreamstudio_token,
            verbose=True,
            engine="stable-diffusion-512-v2-1",
        )

    def generate_image(self, prompt_data: argparse.Namespace, init_image):

        start_schedule = 1.0
        end_schedule = 0.01

        if init_image is not None:
            start_schedule = prompt_data.start_schedule
            end_schedule = prompt_data.end_schedule

        answers = self.conn.generate(prompt=prompt_data.prompt[0], samples=prompt_data.samples,
                                     cfg_scale=prompt_data.cfg_scale, sampler=prompt_data.sampler,
                                     init_image=init_image, start_schedule=start_schedule, end_schedule=end_schedule)

        imgs_bin = []

        for resp in answers:
            for artifact in resp.artifacts:
                if artifact.finish_reason == generation.FILTER:
                    pass
                if artifact.type == generation.ARTIFACT_IMAGE:
                    imgs_bin.append({"binary": io.BytesIO(artifact.binary), "seed": artifact.seed})

        if len(imgs_bin) == 0:
            raise SystemError("Empty images list")

        return imgs_bin


def parse_arguments(message_content):
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--samples', type=int, default=1)
    parser.add_argument('-c', '--cfg_scale', type=float, default=7.0, choices=range(1, 21))
    parser.add_argument('--sampler', type=int, default=7)
    parser.add_argument('--start_schedule', type=float, default=0.6)
    parser.add_argument('--end_schedule', type=float, default=0.1)
    parser.add_argument('--img', type=str, default=None)
    parser.add_argument('prompt', type=str, nargs='+')

    return parser.parse_args(message_content.split("; "))

FROM python:3.10.6-slim-bullseye

ARG bpffmpeg

ARG discord
ARG voice
ARG ibmkey
ARG dreamstudio
ARG openai
ARG redish
ARG redisp
ARG prefix

ENV discord ${discord}
ENV voice ${voice}
ENV ibmkey ${ibmkey}
ENV dreamstudio ${dreamstudio}
ENV openai ${openai}
ENV redish ${redish}
ENV redisp ${redisp}
ENV prefix ${prefix}

WORKDIR /app

COPY requirements.txt requirements.txt

RUN apt update && apt install build-essential libjpeg-dev zlib1g-dev libffi-dev -y && apt install ffmpeg -y && pip install --upgrade pip && pip install -r requirements.txt

CMD ["python3", "./Botinho/Bot.py"]

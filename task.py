# Install required packages:
# pip install moviepy

from moviepy import VideoFileClip

def convert_video_to_audio(video_path, output_audio):
    # Load video
    video = VideoFileClip(video_path)

    # Extract audio
    audio = video.audio

    # Save audio file
    audio.write_audiofile(output_audio)

    print("Conversion Completed!")

# Example
video_file = "sample.mp4"
audio_file = "output.mp3"

convert_video_to_audio(video_file, audio_file)
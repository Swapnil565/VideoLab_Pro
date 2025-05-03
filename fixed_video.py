import os
import sys
import time
import json
import requests
from pathlib import Path
from dotenv import load_dotenv
from pydub import AudioSegment
import assemblyai as aai
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, ImageClip
import subprocess

def create_final_video(original_video_path, ai_audio_path, subtitles_path, output_video_path, b_roll_images=None):
    """
    Create the final video with AI voice, large centered captions, and B-roll images
    """
    print("Creating final video...")
    
    try:
        # Load the original video
        original_video = VideoFileClip(original_video_path)
        
        # Load the AI-generated audio
        ai_audio = AudioFileClip(ai_audio_path)
        
        # Get durations for synchronization
        audio_duration = ai_audio.duration
        video_duration = original_video.duration
        
        print(f"Original video duration: {video_duration:.2f}s")
        print(f"AI audio duration: {audio_duration:.2f}s")
        
        # Ensure the video is at least as long as the audio by looping if needed
        if audio_duration > video_duration:
            print(f"Audio is longer than video. Extending video...")
            # Loop the video to match audio duration
            n_loops = int(audio_duration / video_duration) + 1
            original_video = original_video.loop(n=n_loops).subclip(0, audio_duration)
            print(f"Extended video to {original_video.duration:.2f}s by looping")
        
        # Create a video with the original visuals but AI audio
        video_with_ai_audio = original_video.set_audio(ai_audio)
        
        # Parse the SRT file to get subtitle timings and text
        with open(subtitles_path, 'r', encoding='utf-8') as f:
            srt_content = f.read()
        
        # Extract subtitle entries using regex
        import re
        pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.+?)(?=\n\n|$)'
        matches = re.findall(pattern, srt_content, re.DOTALL)
        
        # Function to convert SRT timestamp to seconds
        def time_to_seconds(time_str):
            h, m, s = time_str.replace(',', '.').split(':')
            return int(h) * 3600 + int(m) * 60 + float(s)
        
        # Create clips for each subtitle and B-roll image
        clips = [video_with_ai_audio]  # Start with the base video
        
        # Add subtitle clips (one word at a time with large, bold text)
        print("Adding large, centered captions to video...")
        for match in matches:
            sub_num, start_time, end_time, text = match
            
            # Convert times to seconds
            start_sec = time_to_seconds(start_time)
            end_sec = time_to_seconds(end_time)
            duration = end_sec - start_sec
            
            # Each subtitle is a single word
            word = text.strip()
            
            # Create a large, bold text clip like in the example image
            try:
                # Try with Impact font first (like meme text)
                txt_clip = TextClip(word, fontsize=120, color='white', bg_color=None,
                                  font='Impact', stroke_color='black', stroke_width=3,
                                  method='caption', size=(video_with_ai_audio.w, None))
            except:
                # Fall back to Arial-Bold if Impact is not available
                txt_clip = TextClip(word, fontsize=120, color='white', bg_color=None,
                                  font='Arial-Bold', method='caption', size=(video_with_ai_audio.w, None))
            
            # Position the text clip in the center of the screen
            txt_clip = txt_clip.set_position('center').set_duration(duration).set_start(start_sec)
            
            # Add the text clip
            clips.append(txt_clip)
        
        print(f"Added {len(matches)} word captions")
        
        # Add B-roll images if available
        if b_roll_images and len(b_roll_images) > 0:
            print(f"Adding {len(b_roll_images)} B-roll images...")
            
            # Calculate timing for B-roll images
            video_duration = video_with_ai_audio.duration
            usable_duration = video_duration * 0.7  # Use 70% of video duration
            start_offset = video_duration * 0.15  # Start after 15% of video
            
            if len(b_roll_images) > 0:
                segment_duration = usable_duration / len(b_roll_images)
            
            # Add each B-roll image
            for i, img_path in enumerate(b_roll_images):
                if os.path.exists(img_path):
                    # Calculate timing
                    start_time = start_offset + (i * segment_duration)
                    image_duration = min(10, segment_duration * 0.9)  # Show each image for up to 10 seconds
                    
                    # Create image clip
                    img_clip = ImageClip(img_path).set_duration(image_duration)
                    
                    # Make image larger (50% of video width)
                    img_clip = img_clip.resize(width=int(video_with_ai_audio.w * 0.5))
                    
                    # Add fade effects
                    img_clip = img_clip.fadein(1).fadeout(1)
                    
                    # Position in top right corner
                    img_clip = img_clip.set_position(("right", "top")).set_start(start_time)
                    
                    # Add to clips
                    clips.append(img_clip)
                    print(f"Added B-roll image at {start_time:.2f}s for {image_duration:.2f}s")
        
        # Create the final composite video
        print("Creating final composite video...")
        final_video = CompositeVideoClip(clips)
        
        # Write the final video to file
        print("Writing final video to file...")
        final_video.write_videofile(output_video_path, codec="libx264", audio_codec="aac")
        
        # Close all clips
        final_video.close()
        original_video.close()
        video_with_ai_audio.close()
        ai_audio.close()
        
        print(f"Final video created and saved to {output_video_path}")
        return output_video_path
    
    except Exception as e:
        print(f"Error creating final video: {e}")
        
        # Fallback method if the main approach fails
        try:
            print("Trying fallback method...")
            
            # Create a basic video with AI audio
            video = VideoFileClip(original_video_path)
            audio = AudioFileClip(ai_audio_path)
            
            # Ensure video is long enough
            if audio.duration > video.duration:
                n_loops = int(audio.duration / video.duration) + 1
                video = video.loop(n=n_loops).subclip(0, audio.duration)
            
            # Set audio
            video = video.set_audio(audio)
            
            # Add subtitles using ffmpeg
            temp_path = "temp_video.mp4"
            video.write_videofile(temp_path, codec="libx264", audio_codec="aac")
            
            command = [
                'ffmpeg', '-y',
                '-i', temp_path,
                '-vf', f'subtitles={subtitles_path}:force_style=\'FontSize=72,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,BorderStyle=3,Outline=2,Shadow=1,Alignment=10\'',
                '-c:a', 'copy',
                output_video_path
            ]
            
            subprocess.run(command, check=True, capture_output=True)
            print("Created video with ffmpeg fallback")
            
            # Clean up
            os.remove(temp_path)
            video.close()
            audio.close()
            
            return output_video_path
        except Exception as fallback_error:
            print(f"Fallback method also failed: {fallback_error}")
            return None

# Test the function
if __name__ == "__main__":
    video_path = r"C:\Users\swapn\OneDrive\Documents\GenerativeAI\1811LABS\WIN_20250424_01_47_53_Pro.mp4"
    audio_path = "ai_voice.mp3"
    srt_path = "subtitles.srt"
    output_path = "fixed_final_video.mp4"
    
    # Get B-roll images
    import glob
    b_roll_images = glob.glob("*.jpg") + glob.glob("*.png")
    
    create_final_video(video_path, audio_path, srt_path, output_path, b_roll_images)

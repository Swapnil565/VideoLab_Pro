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
from moviepy.video.tools.subtitles import SubtitlesClip
from PIL import Image
import io

# Local imports
from caption.create_caption import generate_captions
from caption.emotional_song import create_emotional_transcript
from overlay.create_overlay import add_overlay
from utils.video import process_video
from utils.audio import extract_audio
import config.settings as config

# Load environment variables from .env file
load_dotenv()

# Get AssemblyAI API key from environment variables
ASSEMBLY_API_KEY = os.getenv('ASSEMBLY_API_KEY')
if not ASSEMBLY_API_KEY:
    print("Error: ASSEMBLY_API_KEY not found in environment variables")
    sys.exit(1)

# Configure AssemblyAI client
aai.settings.api_key = ASSEMBLY_API_KEY

def extract_audio_from_video(video_path, output_audio_path):
    """
    Extract audio from video file and save it as WAV
    """
    try:
        print(f"Extracting audio from {video_path}...")
        video = VideoFileClip(video_path)
        video.audio.write_audiofile(output_audio_path, codec='pcm_s16le')
        print(f"Audio extracted and saved to {output_audio_path}")
        return output_audio_path
    except Exception as e:
        print(f"Error extracting audio: {e}")
        sys.exit(1)

def transcribe_audio(audio_path):
    """
    Transcribe audio using AssemblyAI and return transcript
    """
    print("Transcribing audio with AssemblyAI...")
    
    try:
        # Initialize AssemblyAI client
        transcriber = aai.Transcriber()
        
        # Transcribe audio
        transcript = transcriber.transcribe(audio_path)
        
        print("Transcription completed successfully!")
        return transcript
    except Exception as e:
        print(f"Error transcribing audio: {e}")
        return None

def generate_ai_voice(transcript_text, original_audio_duration, voice_name="male"):
    """
    Generate AI voice from transcript using EachLabs OpenVoice with fallback to gTTS
    """
    print(f"Generating AI voice using EachLabs OpenVoice...")
    
    try:
        # First try to use EachLabs OpenVoice for better voice quality and customization
        openvoice_api_key = os.getenv('OPENVOICE_API_KEY')
        if openvoice_api_key and openvoice_api_key.strip() != "":
            try:
                print("Using EachLabs OpenVoice for voice generation...")
                
                # Install requests if not already installed
                try:
                    import requests
                except ImportError:
                    print("Installing required packages...")
                    import subprocess
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
                    import requests
                
                # EachLabs API endpoint for text-to-speech
                url = "https://api.eachlabs.ai/v1/tts"
                
                # Set up the headers with API key
                headers = {
                    "Authorization": f"Bearer {openvoice_api_key}",
                    "Content-Type": "application/json"
                }
                
                # Set up the payload with text and voice settings
                # Using a male voice as requested
                payload = {
                    "text": transcript_text,
                    "voice_id": "male-1",  # Male voice
                    "speed": 1.0,  # Normal speed (will adjust later)
                    "pitch": 1.0,  # Normal pitch
                    "format": "mp3"
                }
                
                # Make the API request
                print("Sending request to EachLabs API...")
                response = requests.post(url, headers=headers, json=payload)
                
                # Check if the request was successful
                if response.status_code == 200:
                    # Save the audio to a temporary file
                    temp_ai_audio_path = "temp_openvoice.mp3"
                    ai_audio_path = "ai_voice.mp3"
                    
                    with open(temp_ai_audio_path, "wb") as f:
                        f.write(response.content)
                    
                    print(f"EachLabs OpenVoice audio generated successfully!")
                    
                    # Load the generated audio to adjust its speed
                    from pydub import AudioSegment
                    audio = AudioSegment.from_file(temp_ai_audio_path)
                    ai_duration = len(audio) / 1000.0  # Duration in seconds
                    
                    # Calculate the speedup factor needed to match original duration
                    speedup_factor = ai_duration / original_audio_duration if original_audio_duration > 0 else 1.0
                    
                    print(f"Original audio duration: {original_audio_duration:.2f} seconds")
                    print(f"OpenVoice audio duration: {ai_duration:.2f} seconds")
                    print(f"Adjusting AI voice speed by factor: {speedup_factor:.2f}")
                    
                    # Adjust the speed if needed
                    if abs(speedup_factor - 1.0) > 0.05:  # Only adjust if difference is significant
                        # Export with adjusted speed using ffmpeg
                        import subprocess
                        
                        # Check if FFMPEG_PATH is set in environment variables
                        ffmpeg_path = os.getenv('FFMPEG_PATH')
                        ffmpeg_command = ffmpeg_path if ffmpeg_path else 'ffmpeg'
                        
                        command = [
                            ffmpeg_command, '-y', '-i', temp_ai_audio_path, 
                            '-filter:a', f'atempo={speedup_factor}', 
                            '-vn', ai_audio_path
                        ]
                        
                        try:
                            subprocess.run(command, check=True, capture_output=True)
                            print(f"AI voice speed adjusted and saved to {ai_audio_path}")
                        except subprocess.CalledProcessError:
                            print("FFmpeg not available, using original speed")
                            audio.export(ai_audio_path, format="mp3")
                    else:
                        # Just use the original if the difference is minimal
                        audio.export(ai_audio_path, format="mp3")
                        print(f"AI voice saved to {ai_audio_path} (no speed adjustment needed)")
                    
                    # Clean up temporary file
                    try:
                        os.remove(temp_ai_audio_path)
                    except:
                        pass
                        
                    return ai_audio_path
                else:
                    print(f"Error with EachLabs API: {response.status_code} - {response.text}")
                    print("Falling back to gTTS...")
            except Exception as openvoice_error:
                print(f"Error with EachLabs OpenVoice: {openvoice_error}")
                print("Falling back to gTTS...")
        else:
            print("EachLabs OpenVoice API key not found, using gTTS instead...")
        
        # Fallback to gTTS if OpenVoice fails or is not configured
        try:
            from gtts import gTTS
            from pydub import AudioSegment
        except ImportError:
            print("Installing required packages...")
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "gtts"])
            from gtts import gTTS
        
        # Generate speech using gTTS
        temp_ai_audio_path = "temp_ai_voice.mp3"
        ai_audio_path = "ai_voice.mp3"
        tts = gTTS(text=transcript_text, lang='en', slow=False)
        tts.save(temp_ai_audio_path)
        
        # Load the generated audio to adjust its speed
        audio = AudioSegment.from_file(temp_ai_audio_path)
        ai_duration = len(audio) / 1000.0  # Duration in seconds
        
        # Calculate the speedup factor needed to match original duration
        speedup_factor = ai_duration / original_audio_duration if original_audio_duration > 0 else 1.0
        
        print(f"Original audio duration: {original_audio_duration:.2f} seconds")
        print(f"AI audio duration: {ai_duration:.2f} seconds")
        print(f"Adjusting AI voice speed by factor: {speedup_factor:.2f}")
        
        # Adjust the speed of the AI audio to match the original duration
        if speedup_factor > 1.05:  # Only adjust if there's a significant difference
            # Export with adjusted speed using ffmpeg
            import subprocess
            
            # Check if FFMPEG_PATH is set in environment variables
            ffmpeg_path = os.getenv('FFMPEG_PATH')
            ffmpeg_command = ffmpeg_path if ffmpeg_path else 'ffmpeg'
            
            command = [
                ffmpeg_command, '-y', '-i', temp_ai_audio_path, 
                '-filter:a', f'atempo={speedup_factor}', 
                '-vn', ai_audio_path
            ]
            
            try:
                subprocess.run(command, check=True, capture_output=True)
                print(f"AI voice speed adjusted and saved to {ai_audio_path}")
            except subprocess.CalledProcessError:
                print("FFmpeg not available, using original speed")
                audio.export(ai_audio_path, format="mp3")
        else:
            # Just use the original if the difference is minimal
            audio.export(ai_audio_path, format="mp3")
            print(f"AI voice saved to {ai_audio_path} (no speed adjustment needed)")
        
        # Clean up temporary file
        try:
            os.remove(temp_ai_audio_path)
        except:
            pass
            
        return ai_audio_path
    except Exception as e:
        print(f"Error generating AI voice: {e}")
        return None

def create_subtitles_file(transcript, output_srt_path, ai_audio_duration=None):
    """
    Create SRT subtitle file from transcript text, synchronized with the AI audio duration
    But instead of sentences, break down into individual words for one-word-at-a-time captions
    """
    print("Creating word-by-word subtitles file...")
    
    try:
        # Use the AI audio duration if provided, otherwise use the transcript duration
        if ai_audio_duration:
            print(f"Using AI audio duration for subtitle timing: {ai_audio_duration:.2f} seconds")
            total_duration = ai_audio_duration
        else:
            # Fallback to transcript duration if AI audio duration is not available
            total_duration = transcript.audio_duration
            print(f"Using transcript duration for subtitle timing: {total_duration:.2f} seconds")
        
        # Get the full transcript text
        full_text = transcript.text
        
        # Split into individual words
        words = full_text.split()
        
        # Calculate approximate duration for each word
        word_duration = total_duration / len(words) if words else 0
        
        # Create SRT file with one word per subtitle
        with open(output_srt_path, 'w', encoding='utf-8') as f:
            current_time = 0
            for i, word in enumerate(words):
                # Format start and end times
                start_time = format_srt_time(current_time * 1000)  # Convert to milliseconds
                end_time = format_srt_time((current_time + word_duration) * 1000)
                
                # Write subtitle entry
                f.write(f"{i+1}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{word}\n\n")
                
                # Update current time for next word
                current_time += word_duration
        
        print(f"Word-by-word subtitles created and saved to {output_srt_path}")
        return output_srt_path
    
    except Exception as e:
        print(f"Error creating subtitles: {e}")
        return None

def format_srt_time(milliseconds):
    """
    Format time in milliseconds to SRT format (HH:MM:SS,mmm)
    """
    if milliseconds is None:
        return "00:00:00,000"
        
    # Convert to seconds
    seconds = milliseconds / 1000
    hours = int(seconds // 3600)
    seconds %= 3600
    minutes = int(seconds // 60)
    seconds %= 60
    millisecs = int((seconds - int(seconds)) * 1000)
    seconds = int(seconds)
    
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millisecs:03d}"

def extract_keywords_from_transcript(transcript_text, num_keywords=5):
    """
    Extract key topics/keywords from the transcript text
    """
    print("Extracting keywords from transcript...")
    
    try:
        # First try to use Groq API for better keyword extraction and prompt enhancement
        groq_api_key = os.getenv('GROQ_API_KEY')
        if groq_api_key and groq_api_key.strip() != "":
            try:
                print("Using Groq API for enhanced keyword extraction...")
                
                # Install requests if not already installed
                try:
                    import requests
                except ImportError:
                    print("Installing required packages...")
                    import subprocess
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
                    import requests
                
                # Groq API endpoint
                url = "https://api.groq.com/openai/v1/chat/completions"
                
                # Set up the headers with API key
                headers = {
                    "Authorization": f"Bearer {groq_api_key}",
                    "Content-Type": "application/json"
                }
                
                # Set up the payload with the prompt
                payload = {
                    "model": "llama3-8b-8192",  # Using Llama 3 model
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an AI assistant that extracts the most visually descriptive keywords from text for image search. Focus on concrete, visual concepts that would make good search terms for finding relevant images."
                        },
                        {
                            "role": "user",
                            "content": f"Extract exactly {num_keywords} visually descriptive keywords or short phrases from this transcript that would be good for searching for relevant images. Return ONLY a JSON array of strings with no explanation: {transcript_text}"
                        }
                    ],
                    "temperature": 0.2
                }
                
                # Make the API request
                print("Sending request to Groq API...")
                response = requests.post(url, headers=headers, json=payload)
                
                # Check if the request was successful
                if response.status_code == 200:
                    try:
                        # Parse the response to get the keywords
                        response_data = response.json()
                        content = response_data['choices'][0]['message']['content']
                        
                        # Try to parse the JSON array from the content
                        import json
                        keywords = json.loads(content)
                        
                        if isinstance(keywords, list) and len(keywords) > 0:
                            print(f"Groq API extracted keywords: {', '.join(keywords)}")
                            return keywords[:num_keywords]
                    except Exception as parse_error:
                        print(f"Error parsing Groq API response: {parse_error}")
                else:
                    print(f"Error from Groq API: {response.status_code} - {response.text}")
            except Exception as groq_error:
                print(f"Error using Groq API: {groq_error}")
                print("Falling back to NLTK for keyword extraction...")
        else:
            print("Groq API key not found, using NLTK for keyword extraction...")
            
        # Fallback to NLTK if Groq API fails or is not configured
        try:
            # Try to import NLTK
            try:
                import nltk
                from nltk.corpus import stopwords
                from nltk.tokenize import word_tokenize
            except ImportError:
                print("Installing required packages...")
                import subprocess
                subprocess.check_call([sys.executable, "-m", "pip", "install", "nltk"])
                import nltk
                from nltk.corpus import stopwords
                from nltk.tokenize import word_tokenize
            
            # Download required NLTK data if not already downloaded
            try:
                nltk.data.find('tokenizers/punkt')
            except LookupError:
                print("Downloading NLTK punkt...")
                nltk.download('punkt')
                
            try:
                nltk.data.find('corpora/stopwords')
            except LookupError:
                print("Downloading NLTK stopwords...")
                nltk.download('stopwords')
            
            # Tokenize the transcript text
            tokens = word_tokenize(transcript_text.lower())
            
            # Remove stopwords and non-alphabetic tokens
            stop_words = set(stopwords.words('english'))
            filtered_tokens = [word for word in tokens if word.isalpha() and word not in stop_words and len(word) > 3]
            
            # Count the frequency of each token
            from collections import Counter
            word_counts = Counter(filtered_tokens)
            
            # Get the most common words as keywords
            keywords = [word for word, count in word_counts.most_common(num_keywords)]
            
            print(f"Extracted keywords: {', '.join(keywords)}")
            
            return keywords
        
        except Exception as e:
            print(f"Error extracting keywords with NLTK: {e}")
            # Return some default keywords if extraction fails
            default_keywords = ["success", "motivation", "journey", "mindset", "freedom"]
            print(f"Using default keywords: {', '.join(default_keywords[:num_keywords])}")
            return default_keywords[:num_keywords]
        
        # Fallback to NLTK if Groq API fails or is not configured
        # Try to import NLTK
        try:
            import nltk
            from nltk.corpus import stopwords
            from nltk.tokenize import word_tokenize
        except ImportError:
            print("Installing required packages...")
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "nltk"])
            import nltk
            from nltk.corpus import stopwords
            from nltk.tokenize import word_tokenize
        
        # Download required NLTK data if not already downloaded
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            print("Downloading NLTK punkt...")
            nltk.download('punkt')
            
        try:
            nltk.data.find('corpora/stopwords')
        except LookupError:
            print("Downloading NLTK stopwords...")
            nltk.download('stopwords')
        
        # Tokenize the transcript text
        tokens = word_tokenize(transcript_text.lower())
        
        # Remove stopwords and non-alphabetic tokens
        stop_words = set(stopwords.words('english'))
        filtered_tokens = [word for word in tokens if word.isalpha() and word not in stop_words and len(word) > 3]
        
        # Count the frequency of each token
        from collections import Counter
        word_counts = Counter(filtered_tokens)
        
        # Get the most common words as keywords
        keywords = [word for word, count in word_counts.most_common(num_keywords)]
        
        print(f"Extracted keywords: {', '.join(keywords)}")
        return keywords
    except Exception as e:
        print(f"Error extracting keywords with NLTK: {e}")
        # Return some default keywords if extraction fails
        default_keywords = ["success", "motivation", "journey", "mindset", "freedom"]
        print(f"Using default keywords: {', '.join(default_keywords[:num_keywords])}")
        return default_keywords[:num_keywords]

def get_unsplash_images(keywords, num_images=5):
    """
    Fetch images from Unsplash based on keywords
    """
    print(f"Fetching images from Unsplash for keywords: {', '.join(keywords)}")
    
    try:
        # Install requests if not already installed
        try:
            import requests
        except ImportError:
            print("Installing requests...")
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
            import requests
        
        # Create a directory for B-roll images if it doesn't exist
        os.makedirs("b_roll", exist_ok=True)
        
        # Enhance keywords for better image search results
        enhanced_keywords = [
            "motivation success",
            "life journey path",
            "confidence mindset",
            "freedom happiness",
            "courage risk taking"
        ]
        
        # Use the enhanced keywords if available, otherwise use the extracted ones
        search_keywords = enhanced_keywords if len(enhanced_keywords) > 0 else keywords
        print(f"Using enhanced keywords for image search: {', '.join(search_keywords[:num_images])}")
        
        # Use Pexels API for more reliable image fetching
        # This is a fallback approach that doesn't require an API key
        image_paths = []
        
        # Distribute images among keywords
        for i, keyword in enumerate(search_keywords[:num_images]):
            try:
                # Format the keyword for URL
                formatted_keyword = keyword.replace(' ', '%20')
                
                # Try different image sources
                urls_to_try = [
                    f"https://source.unsplash.com/1600x900/?{formatted_keyword}",
                    f"https://picsum.photos/1600/900?random={i}&{formatted_keyword}",
                    f"https://loremflickr.com/1600/900/{formatted_keyword}?random={i}"
                ]
                
                success = False
                for url in urls_to_try:
                    try:
                        # Add a random parameter to avoid caching
                        import random
                        url_with_random = f"{url}&r={random.randint(1, 10000)}"
                        
                        # Download the image with a timeout
                        response = requests.get(url_with_random, stream=True, timeout=10)
                        
                        if response.status_code == 200 and len(response.content) > 10000:  # Ensure it's not a tiny image
                            img_path = f"b_roll/{keyword.replace(' ', '_')}_{i}.jpg"
                            with open(img_path, 'wb') as f:
                                f.write(response.content)
                            image_paths.append(img_path)
                            print(f"Downloaded image for '{keyword}'")
                            success = True
                            break
                    except Exception as img_error:
                        print(f"Error with {url}: {img_error}")
                        continue
                
                if not success:
                    print(f"Failed to download image for '{keyword}'")
                    # Create a placeholder colored image instead
                    from PIL import Image
                    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (0, 255, 255)]
                    img = Image.new('RGB', (1600, 900), colors[i % len(colors)])
                    img_path = f"b_roll/placeholder_{keyword.replace(' ', '_')}.jpg"
                    img.save(img_path)
                    image_paths.append(img_path)
                    print(f"Created placeholder image for '{keyword}'")
            except Exception as keyword_error:
                print(f"Error processing keyword '{keyword}': {keyword_error}")
        
        return image_paths
    
    except Exception as e:
        print(f"Error fetching images: {e}")
        # Create placeholder images as fallback
        image_paths = []
        os.makedirs("b_roll", exist_ok=True)
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (0, 255, 255)]
        for i in range(min(num_images, len(colors))):
            from PIL import Image
            img = Image.new('RGB', (1600, 900), colors[i])
            img_path = f"b_roll/fallback_{i+1}.jpg"
            img.save(img_path)
            image_paths.append(img_path)
        print(f"Created {len(image_paths)} fallback images due to error")
        return image_paths

def generate_ai_images(prompts, num_images=5):
    """
    Generate images using Hugging Face's Stable Diffusion API with API key
    """
    print(f"Generating AI images for prompts: {', '.join(prompts)}")
    
    try:
        # Get API key from environment variables
        huggingface_api_key = os.getenv('HUGGINGFACE_API_KEY')
        if not huggingface_api_key or huggingface_api_key.strip() == "":
            print("Warning: HUGGINGFACE_API_KEY not found in .env file. Using API without authentication.")
        
        # Create a directory for AI-generated images
        os.makedirs("b_roll/ai_generated", exist_ok=True)
        
        # First try to use the Hugging Face Inference API (doesn't require local GPU)
        try:
            import requests
            
            image_paths = []
            for i, prompt in enumerate(prompts[:num_images]):
                # Enhance the prompt for better results
                enhanced_prompt = f"high quality, detailed image of {prompt}, 4k, realistic, professional photography"
                
                print(f"Generating image for: '{prompt}' using Hugging Face API")
                
                # API endpoint for Stable Diffusion
                API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
                
                # Prepare headers with API key if available
                headers = {}
                if huggingface_api_key and huggingface_api_key.strip() != "":
                    headers["Authorization"] = f"Bearer {huggingface_api_key}"
                
                # Make API request
                response = requests.post(API_URL, headers=headers, json={"inputs": enhanced_prompt})
                
                # Check if the request was successful
                if response.status_code == 200:
                    # Save the image
                    img_path = f"b_roll/ai_generated/{prompt.replace(' ', '_')}_{i}.png"
                    with open(img_path, "wb") as f:
                        f.write(response.content)
                    image_paths.append(img_path)
                    print(f"Successfully generated and saved image for '{prompt}'")
                else:
                    print(f"Failed to generate image via API: {response.text}")
                    # Try to use local fallback if API fails
                    raise Exception("API request failed, trying local fallback")
            
            # If we successfully generated all images via API, return them
            if len(image_paths) > 0:
                return image_paths
                
        except Exception as api_error:
            print(f"Error using Hugging Face API: {api_error}")
            print("Falling back to local model...")
        
        # Fallback to local model if API fails
        try:
            # Try to import required libraries for local generation
            try:
                import torch
                from diffusers import StableDiffusionPipeline
            except ImportError:
                print("Installing diffusers and torch for local AI image generation...")
                import subprocess
                subprocess.check_call([sys.executable, "-m", "pip", "install", "diffusers", "torch", "transformers", "accelerate"])
                import torch
                from diffusers import StableDiffusionPipeline
            
            # Check if CUDA is available for GPU acceleration
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"Using device: {device} for local image generation")
            
            # Load the model (this will download it the first time)
            model_id = "runwayml/stable-diffusion-v1-5"  # Free model that works well
            pipe = StableDiffusionPipeline.from_pretrained(model_id, torch_dtype=torch.float16 if device == "cuda" else torch.float32)
            pipe = pipe.to(device)
            
            # Generate images for each prompt
            image_paths = []
            for i, prompt in enumerate(prompts[:num_images]):
                # Enhance the prompt for better results
                enhanced_prompt = f"high quality, detailed image of {prompt}, 4k, realistic, professional photography"
                
                # Generate the image
                print(f"Generating image locally for: '{prompt}'")
                image = pipe(enhanced_prompt).images[0]
                
                # Save the image
                img_path = f"b_roll/ai_generated/{prompt.replace(' ', '_')}_{i}.png"
                image.save(img_path)
                image_paths.append(img_path)
                print(f"Successfully generated and saved image locally for '{prompt}'")
            
            return image_paths
            
        except Exception as local_error:
            print(f"Error generating images locally: {local_error}")
            
        # If both API and local generation fail, create placeholder images
        print("Both API and local generation failed. Creating placeholder images.")
        from PIL import Image, ImageDraw, ImageFont
        
        image_paths = []
        for i, prompt in enumerate(prompts[:num_images]):
            # Create a gradient background
            img = Image.new('RGB', (1024, 1024), color=(73, 109, 137))
            d = ImageDraw.Draw(img)
            
            # Add text with the prompt
            try:
                font = ImageFont.truetype("arial.ttf", 36)
            except IOError:
                font = ImageFont.load_default()
                
            d.text((10, 10), f"AI Image: {prompt}", fill=(255, 255, 255), font=font)
            
            # Save the placeholder
            img_path = f"b_roll/ai_generated/placeholder_{prompt.replace(' ', '_')}.png"
            img.save(img_path)
            image_paths.append(img_path)
            print(f"Created placeholder image for '{prompt}'")
        
        return image_paths
    
    except Exception as e:
        print(f"Error in generate_ai_images: {e}")
        return []

def get_b_roll_images(transcript_text, num_images=5, use_ai_generation=False):
    """
    Get B-roll images related to the transcript content using either Unsplash or AI generation
    """
    print("Getting B-roll images...")
    
    # Extract keywords from the transcript
    keywords = extract_keywords_from_transcript(transcript_text, num_images)
    
    # Get images based on the selected method - default to Unsplash as requested
    if use_ai_generation:
        # Generate prompts from keywords
        prompts = [f"{keyword}" for keyword in keywords]
        return generate_ai_images(prompts, num_images)
    else:
        # Use Unsplash to fetch images
        print("Using Unsplash to fetch images...")
        return get_unsplash_images(keywords, num_images)

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
            
            import subprocess
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
                    # Get video duration for positioning B-roll images
                    video_duration = video_with_ai_audio.duration
                    
                    # Distribute images evenly throughout the video
                    # Start after 20% of the video and end before 90% to ensure visibility
                    usable_duration = video_duration * 0.7  # Use 70% of the video duration for images
                    start_offset = video_duration * 0.2  # Start after 20% of the video
                    
                    if len(b_roll_images) > 0:
                        segment_duration = usable_duration / len(b_roll_images)
                    else:
                        segment_duration = usable_duration
                    
                    # Create a list to hold all clips (video + B-roll images)
                    all_clips = [video_with_ai_audio]
                    
                    # Add each B-roll image as a clip with improved visibility
                    for i, img_path in enumerate(b_roll_images):
                        if os.path.exists(img_path):
                            try:
                                # Calculate when to show this image
                                start_time = start_offset + (i * segment_duration)
                                
                                # Make each image appear for longer (8 seconds instead of 5)
                                image_duration = min(8, segment_duration * 0.9)  # Either 8 seconds or 90% of segment
                                
                                # Create image clip
                                img_clip = ImageClip(img_path).set_duration(image_duration)
                                
                                # Size the image to be more prominent (40% of video width instead of 1/3)
                                img_clip = img_clip.resize(width=int(video_with_ai_audio.w * 0.4))
                                
                                # Add a fade in/out effect for smoother transitions
                                img_clip = img_clip.fadein(0.5).fadeout(0.5)
                                
                                # Position in the top right corner with some padding
                                img_clip = img_clip.set_position(("right", "top")).set_start(start_time)
                                
                                # Add to the list of clips
                                all_clips.append(img_clip)
                                print(f"Added B-roll image: {img_path} at time {start_time:.2f}s for {image_duration:.2f}s")
                            except Exception as img_error:
                                print(f"Error adding image {img_path}: {img_error}")
                    
                    # Create a composite video with all clips
                    print("Creating composite video with B-roll images...")
                    final_video = CompositeVideoClip(all_clips)
                    
                    # Write the final video to file
                    print("Writing final video with B-roll images...")
                    final_video.write_videofile(output_video_path, codec="libx264", audio_codec="aac")
                    
                    # Close the composite video
                    final_video.close()
                except Exception as e:
                    print(f"Warning: Could not add B-roll images: {e}")
                    print("Saving video without B-roll images")
                    # If adding B-roll fails, just use the video without them
                    video_with_ai_audio.write_videofile(output_video_path, codec="libx264", audio_codec="aac")
            else:
                # Write the final video to file without B-roll images
                video_with_ai_audio.write_videofile(output_video_path, codec="libx264", audio_codec="aac")
        
        # Close all clips to free resources
        original_video.close()
        ai_audio.close()
        video_with_ai_audio.close()
        
        print(f"Final video created and saved to {output_video_path}")
        return output_video_path
    except Exception as e:
        print(f"Error creating final video: {e}")
        return None

def main():
    # Define file paths
    video_path = r"C:\Users\swapn\OneDrive\Documents\GenerativeAI\1811LABS\WIN_20250424_01_47_53_Pro.mp4"  # Path to your input video
    audio_path = "extracted_audio.wav"  # Temporary audio file path
    srt_path = "subtitles.srt"  # Path for subtitle file
    output_video_path = "final_ai_video.mp4"  # Path for final video
    
    # Step 1: Extract audio from video
    extract_audio_from_video(video_path, audio_path)
    
    # Get original audio duration
    try:
        from pydub import AudioSegment
        original_audio = AudioSegment.from_wav(audio_path)
        original_duration = len(original_audio) / 1000.0  # Duration in seconds
    except Exception as e:
        print(f"Warning: Could not determine original audio duration: {e}")
        original_duration = 0  # Default value
    
    # Step 2: Transcribe audio with AssemblyAI
    transcript = transcribe_audio(audio_path)
    
    if transcript:
        print("\nTranscript:")
        print(transcript.text)
        
        # Step 3: Generate AI voice from transcript using Google Text-to-Speech
        # Pass the original audio duration to match the speed
        ai_audio_path = generate_ai_voice(transcript.text, original_duration)
        
        # Step 4: Create subtitles file with timing based on AI audio
        # Get AI audio duration for better subtitle synchronization
        try:
            from pydub import AudioSegment
            ai_audio = AudioSegment.from_file(ai_audio_path)
            ai_audio_duration = len(ai_audio) / 1000.0  # Duration in seconds
        except Exception as e:
            print(f"Warning: Could not determine AI audio duration: {e}")
            ai_audio_duration = None
            
        subtitles_path = create_subtitles_file(transcript, srt_path, ai_audio_duration)
        
        # Step 5: Get B-roll images - either from Unsplash or AI-generated
        # Set use_ai_generation to True to use AI image generation, False for Unsplash
        use_ai_generation = False  # Using Unsplash images as requested
        num_b_roll_images = 5  # Number of B-roll images to include
        
        print(f"\nGetting B-roll images using {'AI generation' if use_ai_generation else 'Unsplash'}...")
        b_roll_images = get_b_roll_images(
            transcript_text=transcript.text, 
            num_images=num_b_roll_images,
            use_ai_generation=use_ai_generation
        )
        
        # Step 6: Create final video with AI voice and subtitles
        if ai_audio_path:
            final_video_path = create_final_video(
                video_path, 
                ai_audio_path,
                srt_path,
                output_video_path,
                b_roll_images=b_roll_images
            )
            
            if final_video_path:
                print(f"\nSuccess! Your AI video has been created: {final_video_path}")
            else:
                print("Failed to create final video")
        else:
            print("Missing required components for final video")
    else:
        print("Failed to transcribe audio with AssemblyAI")

if __name__ == "__main__":
    main()
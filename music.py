import scipy
from stress import get_stress_music_prompt
import time
from transformers import AutoProcessor, MusicgenForConditionalGeneration

print("Start downloading model...")

'processor = AutoProcessor.from_pretrained("facebook/musicgen-small")'
processor = AutoProcessor.from_pretrained("/Users/xibei/MusicGPT/model")
print("Processor loaded")
'model = MusicgenForConditionalGeneration.from_pretrained("facebook/musicgen-small")'
model = MusicgenForConditionalGeneration.from_pretrained("/Users/xibei/MusicGPT/model")
print("Model loaded")

input_text = get_stress_music_prompt()
print("input_text:", input_text)

inputs = processor(
    text=[input_text],
    padding=True,
    return_tensors="pt"
)

start = time.time()
audio_values = model.generate(
    **inputs,
    max_new_tokens=500,
    temperature=1.2,
    top_k=250,
    top_p=0.9
)
print(time.time() - start) # Log time taken in generation

sampling_rate = model.config.audio_encoder.sampling_rate
scipy.io.wavfile.write("/Users/xibei/Desktop/GraduationProject/InteractiveWebPage/generated_audiomusicgen_out.wav", rate=sampling_rate, data=audio_values[0, 0].numpy())

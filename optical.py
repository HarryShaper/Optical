# IMPORTS
import sys
import os
import re
import cv2
import numpy as np
import easyocr
from tqdm import tqdm
import string

#*********************************************************************#
# CONSTANTS
#*********************************************************************#

LANGUAGES = ['en']
confidence_threshold = 0.3

ROI_PCT = {
	"x": 0.0474,
	"y": 0.3440,
	"w": 0.8853,
	"h": 0.3338
}

# Confusable digits mapping for OCR correction
CONFUSABLE_DIGITS = {
	"1": ["I", "L"],
	"5": ["S"],
	"2": ["Z", "7"],
	"7": ["2"],
	"0": ["O"],
	"9": ["G"]
}

#*********************************************************************#
# DYNAMICALLY FETCH SELECTED FOLDER
#*********************************************************************#

if len(sys.argv) >= 2:
	SHOOT_FOLDER = sys.argv[1]
else:
	SHOOT_FOLDER = r"C:\Users\Harry Shaper\Desktop\test_setref"

if not os.path.isdir(SHOOT_FOLDER):
	print(f"Error: '{SHOOT_FOLDER}' is not a valid folder.")
	sys.exit(1)

#*********************************************************************#
# FUNCTIONS
#*********************************************************************#

# ---------------- IMAGE DESKEW / PREPROCESS ---------------- #

def getSkewAngle(cvImage) -> float:
	newImage = cvImage.copy()
	gray = cv2.cvtColor(newImage, cv2.COLOR_BGR2GRAY)
	blur = cv2.GaussianBlur(gray, (9, 9), 0)
	thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
	kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 5))
	dilate = cv2.dilate(thresh, kernel, iterations=2)
	contours, _ = cv2.findContours(dilate, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
	if len(contours) == 0:
		return 0.0
	contours = sorted(contours, key=lambda c: cv2.contourArea(c), reverse=True)
	largestContour = contours[0]
	minAreaRect = cv2.minAreaRect(largestContour)
	angle = minAreaRect[-1]
	if angle < -45:
		angle = 90 + angle
	return -1.0 * angle

def rotateImage(cvImage, angle: float):
	(h, w) = cvImage.shape[:2]
	center = (w // 2, h // 2)
	M = cv2.getRotationMatrix2D(center, angle, 1.0)
	rotated = cv2.warpAffine(cvImage, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
	return rotated

def deskew(cvImage):
	angle = getSkewAngle(cvImage)
	return rotateImage(cvImage, -1.0 * angle)

def prep_image(image_path: str):
	image = cv2.imread(image_path)
	if image is None:
		print(f"Could not load image: {image_path}")
		return None
	H, W = image.shape[:2]
	x = int(ROI_PCT["x"] * W)
	y = int(ROI_PCT["y"] * H)
	w = int(ROI_PCT["w"] * W)
	h = int(ROI_PCT["h"] * H)
	roi = image[y:y+h, x:x+w]
	roi = deskew(roi)
	gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
	gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
	_, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
	kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
	thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
	return thresh

# ---------------- SANITIZE FOLDER NAME ---------------- #

def sanitize_filename(text):
	if not text:
		return None
	sanitized = re.sub(r'[\\/*?:"<>|]', '', text)
	sanitized = re.sub(r'\s+', '', sanitized)
	return sanitized

# ---------------- CORRECT SLATE USING DOMAIN RULES ---------------- #

used_scenes = set()  # Tracks already processed numeric parts

def correct_slate(ocr_text: str) -> str:
	if not ocr_text:
		return None

	ocr_text = ocr_text.upper().replace(" ", "")
	result = ""
	number_buffer = ""
	stage = "prefix"

	for c in ocr_text:
		# Apply confusable digits
		for k, vals in CONFUSABLE_DIGITS.items():
			if c in vals:
				c = k

		if stage == "prefix":
			if c.isdigit():
				stage = "number"
				number_buffer += c
			else:
				result += c
		elif stage == "number":
			if c.isalpha():
				# Fix numeric buffer before switching to suffix
				number_buffer = fix_confusable_number(number_buffer)
				result += number_buffer
				number_buffer = ""
				stage = "suffix"
				result += c
			elif c.isdigit():
				number_buffer += c
		elif stage == "suffix":
			# Cap first letter if double-letter suffix
			if len(result) > 0 and result[-1].isalpha() and c.isalpha():
				if len(result[-1:]) == 1 and result[-1] > "D":
					c = "A"
			if c.isalpha():
				result += c

	if stage == "number" and number_buffer:
		number_buffer = fix_confusable_number(number_buffer)
		result += number_buffer

	# Register numeric part as used scene
	numeric_part = "".join(filter(str.isdigit, result))
	if numeric_part:
		used_scenes.add(numeric_part)

	return result

# ---------------- CONTEXT-AWARE NUMERIC FIX ---------------- #

def fix_confusable_number(num_str) -> str:
	num_str = str(num_str)
	if not num_str:
		return ""
	alternatives = generate_confusable_numbers(num_str)
	# Pick alternative that matches used scenes if possible
	for alt in alternatives:
		if alt in used_scenes:
			return alt
	return num_str

def generate_confusable_numbers(num_str: str):
	alternatives = set([num_str])
	for i, c in enumerate(num_str):
		for conf, vals in CONFUSABLE_DIGITS.items():
			if c == conf:
				for val in vals:
					alt = num_str[:i] + val + num_str[i+1:]
					alternatives.add(alt)
			elif c in vals:
				alt = num_str[:i] + conf + num_str[i+1:]
				alternatives.add(alt)
	return alternatives

# ---------------- FETCH SLATE DATA USING OCR ---------------- #

reader = easyocr.Reader(LANGUAGES, gpu=True, verbose=False)

def fetch_slate_data(image_path, threshold=confidence_threshold):
	prepped = prep_image(image_path)
	if prepped is None:
		return None
	results = reader.readtext(prepped, detail=1)
	if not results:
		return None
	filtered = [res[1] for res in results if res[2] >= threshold]
	if not filtered:
		return None
	text = ''.join(filtered)
	text = re.sub(r'\s+', '', text)
	text = re.sub(r'[\\/*?:"<>|]', '', text)
	corrected = correct_slate(text)
	return corrected

# ---------------- RENAME FOLDERS BASED ON SLATE ---------------- #

def rename_by_slate():
	folders = [f for f in os.listdir(SHOOT_FOLDER) if os.path.isdir(os.path.join(SHOOT_FOLDER, f))]
	with tqdm(folders, desc="Processing folders", unit="folder", colour='green') as pbar:
		for folder in pbar:
			folder_path = os.path.join(SHOOT_FOLDER, folder)
			jpg_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.jpg')]
			if not jpg_files:
				continue
			last_jpg = os.path.join(folder_path, jpg_files[-1])
			tqdm.write(f"Processing: {last_jpg}")
			slate_text = fetch_slate_data(last_jpg)
			if not slate_text:
				tqdm.write("  ⚠ No confident text found")
				continue
			new_path = os.path.join(SHOOT_FOLDER, slate_text)
			counter = 1
			while os.path.exists(new_path):
				new_path = os.path.join(SHOOT_FOLDER, f"{slate_text}_{counter}")
				counter += 1
			os.rename(folder_path, new_path)
			tqdm.write(f"  ✔ Renamed to: {os.path.basename(new_path)}")
			pbar.update(0)

# ---------------- SHOW IMAGE ---------------- #

def show_image(img, title="Preview", max_dim=1400):
	if img is None:
		print("show_image: image is None")
		return
	h, w = img.shape[:2]
	scale = min(1.0, max_dim / max(h, w))
	if scale < 1.0:
		img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
	cv2.imshow(title, img)
	cv2.waitKey(0)
	cv2.destroyAllWindows()

#*********************************************************************#
# EXECUTION
#*********************************************************************#

if __name__ == "__main__":
	try:
		print("hello")
		rename_by_slate()
	except Exception as e:
		print("\n❌ ERROR:")
		print(e)
		input("\nPress Enter to close...")
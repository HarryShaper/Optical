'''*************************************************
content     Optical - OCR

version     0.0.1
date        21-04-2026

author      Harry Shaper <harryshaper@gmail.com>

*************************************************'''

import sys
import os
import re
import cv2
import easyocr
from tqdm import tqdm
from pathlib import Path


# CONSTANTS
LANGUAGES = ['en']

confidence_threshold = 0.5

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

def resource_path(relative_path):
	if getattr(sys, "frozen", False):
		return Path(sys._MEIPASS) / relative_path

	return Path(__file__).resolve().parents[1] / relative_path


#*********************************************************************#
# BACKEND DETECTION
#*********************************************************************#

def get_torch_backend():
	try:
		import torch

		if torch.cuda.is_available():
			return "cuda"

		if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
			return "mps"

		return "cpu"

	except Exception:
		return "cpu"


TORCH_BACKEND = get_torch_backend()
print(f"OCR backend detected: {TORCH_BACKEND}")


def get_ocr_backend():
	return TORCH_BACKEND


#*********************************************************************#
# FUNCTIONS
#*********************************************************************#

# ---------------- IMAGE DESKEW / PREPROCESS ---------------- #

def getSkewAngle(cvImage) -> float:
	newImage = cvImage.copy()
	gray = cv2.cvtColor(newImage, cv2.COLOR_BGR2GRAY)
	blur = cv2.GaussianBlur(gray, (9, 9), 0)
	thresh = cv2.threshold(
		blur,
		0,
		255,
		cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
	)[1]
	kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 5))
	dilate = cv2.dilate(thresh, kernel, iterations=2)
	contours, _ = cv2.findContours(
		dilate,
		cv2.RETR_LIST,
		cv2.CHAIN_APPROX_SIMPLE
	)

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
	matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
	rotated = cv2.warpAffine(
		cvImage,
		matrix,
		(w, h),
		flags=cv2.INTER_CUBIC,
		borderMode=cv2.BORDER_REPLICATE
	)
	return rotated


def deskew(cvImage):
	angle = getSkewAngle(cvImage)
	return rotateImage(cvImage, -1.0 * angle)


def prep_image(image_path: str):
	image = cv2.imread(image_path)
	if image is None:
		print(f"Could not load image: {image_path}")
		return None

	height, width = image.shape[:2]

	x = int(ROI_PCT["x"] * width)
	y = int(ROI_PCT["y"] * height)
	w = int(ROI_PCT["w"] * width)
	h = int(ROI_PCT["h"] * height)

	roi = image[y:y + h, x:x + w]
	roi = deskew(roi)

	gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
	gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)

	_, thresh = cv2.threshold(
		gray,
		0,
		255,
		cv2.THRESH_BINARY + cv2.THRESH_OTSU
	)

	kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
	thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

	return thresh


# ---------------- SANITIZE / VALIDATE DETECTED TEXT ---------------- #

def normalize_detected_text(text: str) -> str:
	if not text:
		return None

	text = text.upper().strip()

	# Remove illegal filename characters
	text = re.sub(r'[\\/*?:"<>|]', '', text)

	# Replace whitespace and hyphens with underscores
	text = re.sub(r'[\s\-]+', '_', text)

	# Collapse repeated underscores
	text = re.sub(r'_+', '_', text)

	# Trim invalid edge characters
	text = text.strip(' _.')
	return text or None


def looks_like_intentional_label(text: str) -> bool:
	if not text:
		return False

	text = text.strip().upper()

	if len(text) < 3:
		return False

	if not re.search(r'[A-Z]', text):
		return False

	valid_count = sum(ch.isalnum() or ch == '_' for ch in text)
	if valid_count < max(3, int(len(text) * 0.6)):
		return False

	return True


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
				number_buffer = fix_confusable_number(number_buffer)
				result += number_buffer
				number_buffer = ""
				stage = "suffix"
				result += c
			elif c.isdigit():
				number_buffer += c

		elif stage == "suffix":
			if len(result) > 0 and result[-1].isalpha() and c.isalpha():
				if len(result[-1:]) == 1 and result[-1] > "D":
					c = "A"

			if c.isalpha():
				result += c

	if stage == "number" and number_buffer:
		number_buffer = fix_confusable_number(number_buffer)
		result += number_buffer

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
					alt = num_str[:i] + val + num_str[i + 1:]
					alternatives.add(alt)
			elif c in vals:
				alt = num_str[:i] + conf + num_str[i + 1:]
				alternatives.add(alt)

	return alternatives


# ---------------- OCR READER ---------------- #

# Note:
# EasyOCR officially exposes a boolean gpu flag.
# We allow both CUDA and MPS to request accelerated mode here.
# If EasyOCR / environment cannot truly use MPS, it may still behave like CPU.
EASYOCR_DIR = resource_path("assets/easyocr")

reader = easyocr.Reader(
	LANGUAGES,
	gpu=(TORCH_BACKEND in ("cuda", "mps")),
	model_storage_directory=str(EASYOCR_DIR),
	user_network_directory=str(EASYOCR_DIR / "user_network"),
	download_enabled=False,
	verbose=False
)


# ---------------- FETCH SLATE DATA USING OCR ---------------- #

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

	text = " ".join(filtered)
	normalized = normalize_detected_text(text)

	if not looks_like_intentional_label(normalized):
		return None

	return normalized


# ---------------- OPTIONAL FOLDER RENAME HELPER ---------------- #

def rename_by_slate(shoot_folder):
	if not shoot_folder or not os.path.isdir(shoot_folder):
		print(f"Invalid folder: {shoot_folder}")
		return

	folders = [
		f for f in os.listdir(shoot_folder)
		if os.path.isdir(os.path.join(shoot_folder, f))
	]

	with tqdm(folders, desc="Processing folders", unit="folder", colour='green') as pbar:
		for folder in pbar:
			folder_path = os.path.join(shoot_folder, folder)

			jpg_files = [
				f for f in os.listdir(folder_path)
				if f.lower().endswith('.jpg')
			]

			if not jpg_files:
				continue

			last_jpg = os.path.join(folder_path, jpg_files[-1])
			tqdm.write(f"Processing: {last_jpg}")

			slate_text = fetch_slate_data(last_jpg)
			if not slate_text:
				tqdm.write("  ⚠ No confident text found")
				continue

			new_path = os.path.join(shoot_folder, slate_text)
			counter = 1

			while os.path.exists(new_path):
				new_path = os.path.join(shoot_folder, f"{slate_text}_{counter}")
				counter += 1

			os.rename(folder_path, new_path)
			tqdm.write(f"  ✔ Renamed to: {os.path.basename(new_path)}")
			pbar.update(0)


# ---------------- SHOW IMAGE ---------------- #

def show_image(img, title="Preview", max_dim=1400):
	if img is None:
		print("show_image: image is None")
		return

	height, width = img.shape[:2]
	scale = min(1.0, max_dim / max(height, width))

	if scale < 1.0:
		img = cv2.resize(
			img,
			(int(width * scale), int(height * scale)),
			interpolation=cv2.INTER_AREA
		)

	cv2.imshow(title, img)
	cv2.waitKey(0)
	cv2.destroyAllWindows()


#*********************************************************************#
# EXECUTION
#*********************************************************************#

if __name__ == "__main__":
	try:
		if len(sys.argv) < 2:
			print("Usage:")
			print("  python optical_ocr.py <image_path>")
			print("  python optical_ocr.py --rename <folder_path>")
			sys.exit(1)

		if sys.argv[1] == "--rename":
			if len(sys.argv) < 3:
				print("Usage: python optical_ocr.py --rename <folder_path>")
				sys.exit(1)

			shoot_folder = sys.argv[2]
			rename_by_slate(shoot_folder)

		else:
			image_path = sys.argv[1]
			result = fetch_slate_data(image_path)
			print(result if result else "No confident text found")

	except Exception as e:
		print("\nERROR:")
		print(e)
		input("\nPress Enter to close...")
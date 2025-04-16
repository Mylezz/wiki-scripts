import os
import hashlib
import requests
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote
from tqdm import tqdm

# CONFIG
MAX_WORKERS = 10
INPUT_FILE = 'image_list.txt'
OUTPUT_DIR = 'images'
DESC_DIR = 'descs'
ERROR_LOG_FILE = 'error_log.txt'

print("Make sure 'image_list.txt' is in the same folder as this script.\n")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DESC_DIR, exist_ok=True)

# Prompt for base wiki URL
base_wiki_url = input("Enter the base wiki URL (e.g., https://example.fandom.com): ").strip().rstrip('/')
desc_url_template = f"{base_wiki_url}/wiki/Special:Export/File:{{filename}}"

def sha1_hash(filepath):
    h = hashlib.sha1()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

def download_with_progress(url, path, label, error_context):
    try:
        response = requests.get(url, stream=True, timeout=30)
        if response.status_code == 404:
            with open(ERROR_LOG_FILE, 'a', encoding='utf-8') as log:
                log.write(f"{error_context}\t{url}\n")
            return False, "404 Not Found"
        response.raise_for_status()
        total = int(response.headers.get('content-length', 0))
        with open(path, 'wb') as f, tqdm(
            total=total, unit='B', unit_scale=True, desc=label, ncols=80
        ) as bar:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    bar.update(len(chunk))
        return True, ""
    except Exception as e:
        return False, str(e)

def download_image_and_desc(entry):
    filename, url, uploader, size, sha1 = entry
    filepath = os.path.join(OUTPUT_DIR, filename)
    descpath = os.path.join(DESC_DIR, filename + '.desc')
    errors = []

    try:
        download_image = True
        if os.path.exists(filepath):
            actual_size = os.path.getsize(filepath)
            actual_sha1 = sha1_hash(filepath)
            if str(actual_size) == size and actual_sha1 == sha1:
                download_image = False
                print(f"{filename}: already up to date.")
            else:
                print(f"{filename}: hash/size mismatch, re-downloading.")

        if download_image:
            success, error = download_with_progress(url, filepath, f"Image: {filename}", filename)
            if not success:
                errors.append(f"{filename} - image failed: {error}")

        # Always (re)download desc
        desc_url = desc_url_template.format(filename=quote(filename))
        success, error = download_with_progress(desc_url, descpath, f"Desc: {filename}", filename + ".desc")
        if not success:
            errors.append(f"{filename} - desc failed: {error}")

    except Exception as e:
        errors.append(f"{filename} - unexpected error: {e}")

    return errors

def main():
    if os.path.exists(ERROR_LOG_FILE):
        os.remove(ERROR_LOG_FILE)

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        entries = [line.strip().split('\t') for line in f if line.strip()]

    print(f"Starting downloads for {len(entries)} files...\n")

    all_errors = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for result in executor.map(download_image_and_desc, entries):
            all_errors.extend(result)

    print("\nAll downloads completed.")

    if all_errors:
        print("\nThe following errors occurred:")
        for err in all_errors:
            print(" -", err)
        print(f"\n404 errors were logged to {ERROR_LOG_FILE}.")
    else:
        print("\nAll files downloaded successfully.")

if __name__ == '__main__':
    main()

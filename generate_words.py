#!/usr/bin/env python3
"""
Generate Latin words with DALL-E 3 images and upload to the Latin Word of the Day API.

Modes:
  generate          - Generate new words (GPT-4o) + images (DALL-E 3) and upload to API
  regenerate-images - Regenerate missing images for words already in the DB
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

OPENAI_API_URL = "https://api.openai.com/v1"
BATCH_SIZE = 25


def get_api_key():
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("OPENAI_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip("'\"")
    if not key:
        print("Error: OPENAI_API_KEY not set. Export it or add to .env file.")
        sys.exit(1)
    return key


def openai_request(api_key, endpoint, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{OPENAI_API_URL}/{endpoint}",
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    resp = urllib.request.urlopen(req, timeout=120)
    return json.loads(resp.read())


def generate_image(api_key, word, output_dir):
    """Generate a DALL-E 3 image for a Latin word."""
    output_path = output_dir / f"{word.lower()}.jpg"
    if output_path.exists() and output_path.stat().st_size > 1000:
        print(f"  Image already exists: {output_path.name}")
        return output_path.name

    prompt = (
        f"A beautiful, artistic illustration representing the Latin word '{word}'. "
        f"Classical Roman aesthetic, warm lighting, painterly style. "
        f"No text or letters in the image."
    )

    try:
        result = openai_request(api_key, "images/generations", {
            "model": "dall-e-3",
            "prompt": prompt,
            "n": 1,
            "size": "1024x1024",
            "response_format": "url",
        })
        image_url = result["data"][0]["url"]
        img_data = urllib.request.urlopen(image_url, timeout=60).read()
        output_path.write_bytes(img_data)
        print(f"  Generated image: {output_path.name} ({len(img_data)} bytes)")
        return output_path.name
    except Exception as e:
        print(f"  ERROR generating image for {word}: {e}")
        return None


def generate_words_batch(api_key, count, exclude_words):
    """Generate a batch of Latin words using GPT-4o."""
    exclude_str = ", ".join(sorted(exclude_words)) if exclude_words else "none"
    prompt = f"""Generate exactly {count} Latin vocabulary words. For each word provide:
- word: the Latin word (capitalized)
- definition: 1-2 sentence English definition starting with "X means..."
- pronunciation: phonetic pronunciation
- origin: brief etymology
- example0/example0_latin: English sentence using the concept / Latin translation
- example1/example1_latin: another pair
- example2/example2_latin: another pair
- synonyms: array of 2 Latin synonyms
- antonyms: array (can be empty)

DO NOT include any of these words: {exclude_str}

Return valid JSON array only, no markdown."""

    result = openai_request(api_key, "chat/completions", {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.9,
        "max_tokens": 16000,
    })
    text = result["choices"][0]["message"]["content"].strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(text)


def upload_word(api_url, word_data):
    """Upload a word to the API."""
    data = json.dumps(word_data).encode()
    req = urllib.request.Request(
        f"{api_url}/items",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read())


def get_existing_words(api_url):
    """Fetch all existing words from the API."""
    req = urllib.request.Request(f"{api_url}/items")
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read())


def update_word_image(api_url, word_id, image_name):
    """Update a word's image field via the API."""
    data = json.dumps({"image": image_name}).encode()
    req = urllib.request.Request(
        f"{api_url}/items/{word_id}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read())


def cmd_generate(args):
    """Generate new words with images."""
    api_key = get_api_key()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get existing words to avoid duplicates
    existing_images = {f.stem for f in output_dir.iterdir() if f.suffix in ('.jpg', '.jpeg', '.png', '.avif')}
    try:
        existing_words_data = get_existing_words(args.api_url)
        existing_names = {w.get("word", "").lower() for w in existing_words_data}
    except Exception:
        existing_names = set()

    exclude = existing_images | existing_names
    print(f"Found {len(existing_images)} existing images, {len(existing_names)} existing words")
    print(f"Excluding {len(exclude)} words total\n")

    all_words = []
    remaining = args.count

    while remaining > 0:
        batch = min(remaining, BATCH_SIZE)
        print(f"[Batch] Generating {batch} words with GPT-4o...")

        words = generate_words_batch(api_key, batch, exclude)
        # Filter out duplicates
        new_words = [w for w in words if w["word"].lower() not in exclude]
        for w in new_words:
            exclude.add(w["word"].lower())

        print(f"  Got {len(new_words)} new words")

        # Generate images
        for w in new_words:
            print(f"\n  Processing: {w['word']}")
            img = generate_image(api_key, w["word"], output_dir)
            if img:
                w["image"] = img

        all_words.extend(new_words)
        remaining -= len(new_words)

        if remaining > 0:
            time.sleep(1)

    # Upload words
    print(f"\nUploading {len(all_words)} words to API...")
    uploaded = 0
    for w in all_words:
        try:
            upload_word(args.api_url, w)
            print(f"  Uploaded: {w['word']}")
            uploaded += 1
        except Exception as e:
            print(f"  ERROR uploading {w['word']}: {e}")

    print(f"\nDone! Uploaded {uploaded}/{len(all_words)} words")


def cmd_regenerate_images(args):
    """Regenerate missing images for existing words in the DB."""
    api_key = get_api_key()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    existing_images = {f.name for f in output_dir.iterdir() if f.suffix in ('.jpg', '.jpeg', '.png', '.avif')}
    print(f"Found {len(existing_images)} images on disk")

    # Get all words from API
    words = get_existing_words(args.api_url)
    print(f"Found {len(words)} words in database")

    # Find words with missing images
    missing = []
    for w in words:
        img = w.get("image", "")
        if not img:
            missing.append(w)
        elif img not in existing_images:
            missing.append(w)

    # Deduplicate by image name
    seen = set()
    unique_missing = []
    for w in missing:
        img = w.get("image", f"{w['word'].lower()}.jpg")
        if img not in seen:
            seen.add(img)
            unique_missing.append(w)

    print(f"Missing {len(unique_missing)} unique images\n")

    generated = 0
    failed = 0
    for i, w in enumerate(unique_missing, 1):
        word = w["word"]
        print(f"[{i}/{len(unique_missing)}] {word}")
        img = generate_image(api_key, word, output_dir)
        if img:
            generated += 1
            # Update word if it had no image field
            if not w.get("image"):
                try:
                    update_word_image(args.api_url, w["id"], img)
                    print(f"  Updated DB image field for {word}")
                except Exception as e:
                    print(f"  Warning: couldn't update DB for {word}: {e}")
        else:
            failed += 1

        # Rate limit: DALL-E 3 has limits
        if i % 5 == 0:
            time.sleep(2)

    print(f"\nDone! Generated {generated} images, {failed} failed")


def main():
    parser = argparse.ArgumentParser(description="Latin Word of the Day generator")
    parser.add_argument("--api-url", default="http://localhost:3000",
                        help="Backend API URL (default: http://localhost:3000)")
    parser.add_argument("--output-dir", default="./images",
                        help="Directory to save generated images")

    sub = parser.add_subparsers(dest="command")

    gen = sub.add_parser("generate", help="Generate new words with images")
    gen.add_argument("--count", type=int, default=25, help="Number of words to generate")

    sub.add_parser("regenerate-images", help="Regenerate missing images for existing DB words")

    args = parser.parse_args()

    if args.command == "generate":
        cmd_generate(args)
    elif args.command == "regenerate-images":
        cmd_regenerate_images(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

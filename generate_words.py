#!/usr/bin/env python3
"""
Generate Latin words with images and upload to the Latin Word of the Day API.

Image sources:
  dalle   - DALL-E 3 (requires OPENAI_API_KEY, costs money)
  pixabay - Pixabay stock photos (requires PIXABAY_API_KEY, free)

Modes:
  generate          - Generate new words (GPT-4o) + images and upload to API
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
PIXABAY_API_URL = "https://pixabay.com/api/"
BATCH_SIZE = 25

# Map Latin words to English search terms for stock photo lookups
LATIN_TO_ENGLISH = {
    "aequor": "ocean sea", "aestas": "summer", "agricola": "farmer field",
    "alacritas": "enthusiasm joy", "alvus": "belly body", "anus": "elderly woman",
    "arbiter": "judge court", "arx": "fortress citadel", "astrum": "star night sky",
    "auris": "ear listening", "avis": "bird flying", "bellator": "warrior battle",
    "caligo": "fog mist dark", "candor": "bright white radiance", "canis": "dog",
    "cano": "singing song", "carmen": "poem song", "castellum": "castle fortress",
    "castra": "military camp", "celer": "fast speed running", "cervus": "deer stag",
    "cibus": "food feast", "cicatrix": "scar wound", "claritas": "clarity brightness",
    "clarus": "famous bright", "clavis": "key lock", "contemplatio": "meditation contemplation",
    "dies": "day sunrise", "digitus": "finger hand", "dominus": "lord master",
    "domum": "home house", "domus": "roman house villa", "dubium": "doubt uncertainty",
    "duo": "two pair", "equus": "horse galloping", "fatum": "fate destiny",
    "febris": "fever illness", "ferrum": "iron metal sword", "flamma": "flame fire",
    "flosculum": "small flower blossom", "fulgur": "lightning bolt", "fulguratio": "lightning storm",
    "fulmen": "thunderbolt storm", "furca": "fork pitchfork", "furtum": "theft shadow",
    "galea": "roman helmet armor", "gaudium": "joy happiness celebration",
    "glacies": "ice glacier frozen", "herba": "herb green plant", "hereditas": "inheritance legacy",
    "lacerta": "lizard reptile", "lacrima": "tear crying", "libertas": "liberty freedom statue",
    "locus": "place location landscape", "ludus": "game play sport",
    "luna": "moon night", "lupus": "wolf", "magnitudo": "greatness mountain grand",
    "mater": "mother child", "mel": "honey bee", "metus": "fear dark",
    "mola": "millstone grinding", "mons": "mountain peak", "monstrum": "monster creature",
    "mundus": "world earth globe", "murmur": "whisper stream water",
    "nidus": "nest bird eggs", "nimbus": "storm cloud rain", "nubes": "clouds sky",
    "oblivio": "forgotten ruins ancient", "otium": "leisure relaxation garden",
    "pavo": "peacock feathers", "paxillus": "wooden stake peg", "pectus": "chest heart",
    "penna": "feather quill writing", "piscis": "fish underwater", "pluvia": "rain drops",
    "poeta": "poet writing book", "pons": "bridge river stone", "pugna": "fight battle combat",
    "rana": "frog pond", "regnum": "kingdom crown castle", "rosa": "rose flower red",
    "sagacitas": "wisdom owl clever", "sagitta": "arrow archery bow",
    "sanguis": "blood red", "saxum": "rock boulder stone", "sibilus": "wind whistle breeze",
    "sol": "sun sunrise golden", "somnium": "dream clouds sleeping",
    "somnolentia": "sleepy drowsy bed", "sonus": "sound music waves",
    "speculum": "mirror reflection", "tauri": "bull horns", "tempestas": "storm tempest sea",
    "umbra": "shadow dark silhouette", "ursus": "bear wild", "valle": "valley green landscape",
    "velleitas": "wish desire candle", "volucris": "bird flight wings",
    "voluntas": "will determination path", "vulcanus": "volcano fire eruption",
    "vultur": "vulture bird prey",
}


def get_env_key(key_name):
    val = os.environ.get(key_name, "")
    if not val:
        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith(f"{key_name}="):
                    val = line.split("=", 1)[1].strip().strip("'\"")
    return val


def get_api_key():
    key = get_env_key("OPENAI_API_KEY")
    if not key:
        print("Error: OPENAI_API_KEY not set. Export it or add to .env file.")
        sys.exit(1)
    return key


def get_pixabay_key():
    key = get_env_key("PIXABAY_API_KEY")
    if not key:
        print("Error: PIXABAY_API_KEY not set.")
        print("Get a free key at https://pixabay.com/api/docs/ (no credit card needed)")
        print("Then add PIXABAY_API_KEY=your-key to .env")
        sys.exit(1)
    return key


def openai_request(api_key, endpoint, payload, retries=3):
    data = json.dumps(payload).encode()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                f"{OPENAI_API_URL}/{endpoint}",
                data=data,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            resp = urllib.request.urlopen(req, timeout=180)
            return json.loads(resp.read())
        except Exception as e:
            if attempt < retries - 1:
                wait = (attempt + 1) * 10
                print(f"  Retry {attempt + 1}/{retries} after error: {e}")
                time.sleep(wait)
            else:
                raise


def fetch_pixabay_image(pixabay_key, word, output_dir):
    """Download a relevant image from Pixabay for a Latin word."""
    output_path = output_dir / f"{word.lower()}.jpg"
    if output_path.exists() and output_path.stat().st_size > 1000:
        print(f"  Image already exists: {output_path.name}")
        return output_path.name

    search_term = LATIN_TO_ENGLISH.get(word.lower(), word.lower())
    params = urllib.parse.urlencode({
        "key": pixabay_key,
        "q": search_term,
        "image_type": "photo",
        "orientation": "horizontal",
        "min_width": 800,
        "per_page": 5,
        "safesearch": "true",
    })
    url = f"{PIXABAY_API_URL}?{params}"

    try:
        resp = urllib.request.urlopen(url, timeout=30)
        data = json.loads(resp.read())
        if not data.get("hits"):
            # Fallback: try just the first word of the search term
            fallback = search_term.split()[0]
            params = urllib.parse.urlencode({
                "key": pixabay_key, "q": fallback, "image_type": "photo",
                "orientation": "horizontal", "min_width": 800, "per_page": 5,
                "safesearch": "true",
            })
            resp = urllib.request.urlopen(f"{PIXABAY_API_URL}?{params}", timeout=30)
            data = json.loads(resp.read())

        if not data.get("hits"):
            print(f"  No Pixabay results for '{search_term}'")
            return None

        # Use the top result's large image
        image_url = data["hits"][0]["largeImageURL"]
        img_data = urllib.request.urlopen(image_url, timeout=60).read()
        output_path.write_bytes(img_data)
        print(f"  Downloaded: {output_path.name} ({len(img_data)} bytes) [{search_term}]")
        return output_path.name
    except Exception as e:
        print(f"  ERROR fetching Pixabay image for {word}: {e}")
        return None


def generate_image_dalle(api_key, word, output_dir):
    """Generate a DALL-E 3 image for a Latin word."""
    output_path = output_dir / f"{word.lower()}.jpg"
    if output_path.exists() and output_path.stat().st_size > 1000:
        print(f"  Image already exists: {output_path.name}")
        return output_path.name

    prompt = (
        f"No text, no letters, no words. "
        f"An artistic representation of the word '{word}'. "
        f"Classical Roman aesthetic, warm lighting, painterly style."
    )

    for attempt in range(3):
        try:
            result = openai_request(api_key, "images/generations", {
                "model": "dall-e-2",
                "prompt": prompt,
                "n": 1,
                "size": "512x512",
                "response_format": "url",
            })
            image_url = result["data"][0]["url"]
            img_data = urllib.request.urlopen(image_url, timeout=120).read()
            output_path.write_bytes(img_data)
            print(f"  Generated image: {output_path.name} ({len(img_data)} bytes)")
            return output_path.name
        except Exception as e:
            if attempt < 2:
                print(f"  Retry image {attempt + 1}/3: {e}")
                time.sleep(10)
            else:
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

    if args.image_source == "pixabay":
        pixabay_key = get_pixabay_key()

    existing_images = {f.stem for f in output_dir.iterdir() if f.suffix in ('.jpg', '.jpeg', '.png', '.avif')}
    try:
        existing_words_data = get_existing_words(args.api_url)
        existing_names = {w.get("word", "").lower() for w in existing_words_data}
    except Exception:
        existing_names = set()

    # Only exclude actual Latin word names from the GPT prompt (not English image filenames)
    exclude = set(existing_names)
    # Track images separately to avoid regenerating existing ones
    existing_image_stems = set(existing_images)
    print(f"Found {len(existing_images)} existing images, {len(existing_names)} existing words")
    print(f"Excluding {len(exclude)} Latin words from generation\n")

    all_words = []
    remaining = args.count

    while remaining > 0:
        batch = min(remaining, BATCH_SIZE)
        print(f"[Batch] Generating {batch} words with GPT-4o...")

        words = generate_words_batch(api_key, batch, exclude)
        new_words = [w for w in words if w["word"].lower() not in exclude]
        for w in new_words:
            exclude.add(w["word"].lower())

        print(f"  Got {len(new_words)} new words")

        for w in new_words:
            print(f"\n  Processing: {w['word']}")
            if args.image_source == "pixabay":
                img = fetch_pixabay_image(pixabay_key, w["word"], output_dir)
            else:
                img = generate_image_dalle(api_key, w["word"], output_dir)
            if img:
                w["image"] = img

        all_words.extend(new_words)
        remaining -= len(new_words)

        if remaining > 0:
            time.sleep(1)

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
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.image_source == "pixabay":
        pixabay_key = get_pixabay_key()
        image_fn = lambda word: fetch_pixabay_image(pixabay_key, word, output_dir)
    else:
        api_key = get_api_key()
        image_fn = lambda word: generate_image_dalle(api_key, word, output_dir)

    existing_images = {f.name for f in output_dir.iterdir() if f.suffix in ('.jpg', '.jpeg', '.png', '.avif')}
    print(f"Found {len(existing_images)} images on disk")

    words = get_existing_words(args.api_url)
    print(f"Found {len(words)} words in database")

    missing = []
    for w in words:
        img = w.get("image", "")
        if not img:
            missing.append(w)
        elif img not in existing_images:
            missing.append(w)

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
        img = image_fn(word)
        if img:
            generated += 1
            if not w.get("image"):
                try:
                    update_word_image(args.api_url, w["id"], img)
                    print(f"  Updated DB image field for {word}")
                except Exception as e:
                    print(f"  Warning: couldn't update DB for {word}: {e}")
        else:
            failed += 1

        if i % 5 == 0:
            time.sleep(1)

    print(f"\nDone! Generated {generated} images, {failed} failed")


def cmd_deploy(args):
    """Deploy generated images and words to production.

    Workflow:
    1. Copy images to server via SCP
    2. Fetch words from local and production APIs
    3. Upload new words to production
    """
    import subprocess

    image_dir = Path(args.output_dir)
    ssh_host = args.ssh_host
    server_img_dir = args.server_img_dir
    prod_api = args.prod_api

    # Step 1: Copy images to server
    images = list(image_dir.glob("*.jpg")) + list(image_dir.glob("*.png"))
    if images:
        print(f"Copying {len(images)} images to server...")
        subprocess.run(
            ["scp", *[str(img) for img in images], f"{ssh_host}:{server_img_dir}/"],
            check=True,
        )
        print(f"  Copied {len(images)} images")
    else:
        print("No images to copy")

    # Step 2: Compare local and production words
    print("\nFetching words from local API...")
    local_words = get_existing_words(args.api_url)

    print("Fetching words from production API...")
    prod_words = get_existing_words(prod_api)
    prod_names = {w["word"].lower() for w in prod_words}

    # Step 3: Upload new words
    new_words = [w for w in local_words if w["word"].lower() not in prod_names]
    print(f"Found {len(new_words)} new words to upload")

    uploaded = 0
    for w in new_words:
        word_data = {k: v for k, v in w.items() if k != "id"}
        try:
            upload_word(prod_api, word_data)
            print(f"  Uploaded: {w['word']}")
            uploaded += 1
        except Exception as e:
            print(f"  ERROR uploading {w['word']}: {e}")

    print(f"\nDone! Uploaded {uploaded}/{len(new_words)} words")


def main():
    parser = argparse.ArgumentParser(description="Latin Word of the Day generator")
    parser.add_argument("--api-url", default="http://localhost:3000",
                        help="Backend API URL (default: http://localhost:3000)")
    parser.add_argument("--output-dir", default="./images",
                        help="Directory to save generated images")
    parser.add_argument("--image-source", choices=["dalle", "pixabay"], default="pixabay",
                        help="Image source: dalle (paid) or pixabay (free, default)")

    sub = parser.add_subparsers(dest="command")

    gen = sub.add_parser("generate", help="Generate new words with images")
    gen.add_argument("--count", type=int, default=25, help="Number of words to generate")

    sub.add_parser("regenerate-images", help="Regenerate missing images for existing DB words")

    deploy = sub.add_parser("deploy", help="Deploy new words and images to production")
    deploy.add_argument("--ssh-host", default="latin",
                        help="SSH host alias for the server (default: latin)")
    deploy.add_argument("--server-img-dir", default="/root/latinWordOfTheDayBE/src/static/img",
                        help="Image directory on the server")
    deploy.add_argument("--prod-api", default="http://latinwordoftheday.com:3000",
                        help="Production API URL (default: http://latinwordoftheday.com:3000)")

    args = parser.parse_args()

    if args.command == "generate":
        cmd_generate(args)
    elif args.command == "regenerate-images":
        cmd_regenerate_images(args)
    elif args.command == "deploy":
        cmd_deploy(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

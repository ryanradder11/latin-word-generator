# Latin Word Generator

Generates Latin vocabulary words (via GPT-4o) with images and uploads them to the Latin Word of the Day API.

## Setup

```bash
cp .env.example .env
# Add your keys to .env:
#   OPENAI_API_KEY=sk-...        (required for word generation and DALL-E images)
#   PIXABAY_API_KEY=...          (required for Pixabay images, free at https://pixabay.com/api/docs/)
```

## Usage

### Generate new words locally

Start the backend first, then generate:

```bash
# Terminal 1: start local backend
cd ../latinWordOfTheDayBe
npm run dev

# Terminal 2: generate words
python generate_words.py generate --count 10
```

Options:
- `--count N` — number of words to generate (default: 25)
- `--image-source dalle` — use DALL-E 2 for images (paid, ~$0.016/image at 256x256)
- `--image-source pixabay` — use Pixabay stock photos (free, default)
- `--output-dir ./images` — where to save images (default: `./images`)

### Regenerate missing images

For words already in the database that are missing images:

```bash
python generate_words.py regenerate-images
```

### Deploy to production

After generating words locally, deploy them to production in one command:

```bash
python generate_words.py deploy
```

This automatically:
1. Copies images to the server via SCP (`/root/latinWordOfTheDayBE/src/static/img/`)
2. Compares local and production words to find new ones
3. Uploads only **new** words to the production API (port 3000)

Options:
- `--ssh-host latin` — SSH host alias (default: `latin`)
- `--server-img-dir /path/to/img` — image directory on the server
- `--prod-api http://latinwordoftheday.com:3000` — production API URL

### Full workflow example

```bash
# 1. Generate 10 new words with free Pixabay images
python generate_words.py generate --count 10

# 2. Deploy to production
python generate_words.py deploy
```

## Image sources

| Source | Cost | Quality | Flag |
|---|---|---|---|
| Pixabay (default) | Free | Stock photos | `--image-source pixabay` |
| DALL-E 2 | ~$0.016/image | AI-generated 256x256 | `--image-source dalle` |

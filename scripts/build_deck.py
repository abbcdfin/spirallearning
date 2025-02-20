import os
import re
import sys
import base64
import shutil
import argparse
import copy
from urllib.parse import urlparse
import hashlib

def generate_id_from_filename(filename):
    """Generates a unique ID from the given filename using a hash algorithm."""
    basename = os.path.basename(filename).replace('.md', '')
    return hashlib.md5(basename.encode()).hexdigest()[:8]

def write_markdown_datablocks_to_file(datablock_match, file_id, output_dir):
    datablock_name = datablock_match.group(1)
    datablock_extension = datablock_match.group(2)
    datablock_filename = f'{datablock_name}-{file_id}.{datablock_extension}'
    datablock_path = os.path.join(output_dir, datablock_filename)
    datablock_data = datablock_match.group(3)
    datablock_bytes = base64.b64decode(datablock_data)
    with open(datablock_path, 'wb') as datablock_file:
        datablock_file.write(datablock_bytes)

def unescape_brackets(text):
    """Unescapes square brackets in the given text."""
    unescaped = text.replace(r'\[', r'[').replace(r'\]', r']')
    return unescaped

def escape_quotes(text):
    """Escapes double quotes in the given text."""
    return text.replace('"', '""')

def convert_markdown_image_tag(text, file_id):
    """Converts markdown image tags like '![][image_name]' to HTML <img> tags."""
    pattern = r'!\[\]\[(.*?)]'
    replacement = lambda match: f'<img src="{match.group(1)}-{file_id}.png">'
    converted_text = re.sub(pattern, replacement, text)
    return converted_text

def parse_markdown(input_file, output_dir):
    questions = []
    current_question = {}
    file_id = generate_id_from_filename(input_file)

    media_dir = os.path.join(output_dir, 'media')
    os.makedirs(media_dir, exist_ok=True)

    with open(input_file, 'r') as file:
        for line in file:
            datablock_regex = re.compile(r"\[(.*?)\]: <data:image\/(\w+);base64,(.*)>")
            datablock_match = datablock_regex.match(line)
            if datablock_match:
                write_markdown_datablocks_to_file(datablock_match, file_id, media_dir)
                continue

            title_regex = re.compile(r'\d+-\\\[ct-.+\\\]')
            title_match = title_regex.match(line)
            if title_match:
                if 'title' in current_question:
                    questions.append(copy.deepcopy(current_question))

                line = unescape_brackets(line)
                current_question['title'] = line.strip()
                current_question['body'] = []

            else:
                if 'title' in current_question:
                    line = convert_markdown_image_tag(line, file_id)
                    line = escape_quotes(line)
                    current_question['body'].append(line.strip())

    return questions

def handle_images(body, output_dir):
    media_dir = os.path.join(output_dir, 'media')
    os.makedirs(media_dir, exist_ok=True)
    
    def replace_image(match):
        img_tag = match.group(0)
        img_src = match.group(1)
        
        if img_src.startswith('data:image'):
            # Handle base64 encoded images
            img_data = re.search(r'base64,(.*)', img_src).group(1)
            img_bytes = base64.b64decode(img_data)
            img_filename = os.path.join(media_dir, f'image_{len(os.listdir(media_dir))}.png')
            with open(img_filename, 'wb') as img_file:
                img_file.write(img_bytes)
            return f'![]({img_filename})'
        elif urlparse(img_src).scheme in ('http', 'https'):
            # Handle images linked via URLs
            return img_tag
        else:
            # Handle local image paths
            img_filename = os.path.join(media_dir, os.path.basename(img_src))
            shutil.copy(img_src, img_filename)
            return f'![]({img_filename})'
    
    body = re.sub(r'!\[.*?\]\((.*?)\)', replace_image, body)
    return body

def generate_anki_file(questions, output_file, output_dir):
    with open(output_file, 'w') as file:
        file.write('Front;Back\n')
        for question in questions:
            title = question['title']
            body = '<br>'.join(question['body'])
            body = handle_images(body, output_dir)
            file.write(f'\"{title}<br>{body}\n\n\"\n')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Convert Google Doc exported Markdown files into AnkiWeb-compatible decks.')
    parser.add_argument('input_directory', type=str, nargs='?', default='./resources', help='Path to the directory containing Markdown files')
    parser.add_argument('output_directory', type=str, nargs='?', default='/tmp/anki', help='Path to the desired output directory for the generated Anki deck .txt files')
    
    args = parser.parse_args()
    
    input_dir = args.input_directory
    output_dir = args.output_directory
    
    if not os.path.isdir(input_dir):
        print(f"Error: Input directory '{input_dir}' does not exist.")
        sys.exit(1)
    
    os.makedirs(output_dir, exist_ok=True)
    
    all_questions = []
    
    for filename in os.listdir(input_dir):
        if filename.endswith('.md'):
            input_file = os.path.join(input_dir, filename)
            questions = parse_markdown(input_file, output_dir)
            all_questions.extend(questions)
    
    output_file = os.path.join(output_dir, 'combined_deck.txt')
    generate_anki_file(all_questions, output_file, output_dir)
    
    print(f"Anki deck generated in '{output_file}'")
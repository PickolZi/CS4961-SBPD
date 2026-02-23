"""
BoxNote to HTML Parser
Author: XZhouQD
Since: Dec 30 2022
Github link: https://github.com/XZhouQD/boxnote-converter

Modified by PickolZi
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Union

from boxnote_to_html_parser import html_mapper

log_format = "%(asctime)s:[%(levelname)s]:%(message)s"
logging.basicConfig(format=log_format, level=logging.INFO)
logger = logging.getLogger()
token = None
user = None


def parse(
        boxnote_content: Union[str, bytes, bytearray],
        title: str = None,
        workdir: Path = None,
        access_token: str = None,
        user_id: str = None) -> str:
    """
    Parse BoxNote to HTML
    """
    global token
    token = access_token if access_token else token
    global user
    user = user_id if user_id else user
    try:
        boxnote = json.loads(boxnote_content)
    except json.JSONDecodeError as e:
        logger.error('Invalid BoxNote content: JSON parse failed')
        raise e
    
    if 'doc' not in boxnote:
        logger.error('Invalid BoxNote content: no doc field')
        raise ValueError('Invalid BoxNote content: no doc field')

    if 'content' not in boxnote.get('doc', {}):
        logger.error('Invalid BoxNote content: no content field')
        raise ValueError('Invalid BoxNote content: no content field')

    contents = ['<!DOCTYPE html>', '<html>', f'{html_mapper.get_base_style()}', '<head>', '<meta charset="UTF-8">', f'<title>{title}</title>', '</head>', '<body>']

    parse_content(boxnote.get('doc', {}).get('content', {}), contents, title, workdir)

    contents = list(filter(lambda x: x is not None, contents))
    contents.extend(['</body>', '</html>'])
    result = ''.join(contents)
    result = str.replace(result, '<p style="text-align: left"></p>', '')  # remove empty paragraph
    return result


def parse_content(
        content: Union[Dict, List],
        contents: List[str],
        title: str,
        workdir: Path,
        ignore_paragraph: bool = False) -> None:
    """
    Parse BoxNote content
    """
    if not content:
        return

    if isinstance(content, list):
        for item in content:
            parse_content(item, contents, title, workdir, ignore_paragraph)
        return

    if not isinstance(content, dict):
        return

    if 'type' not in content:
        logger.error('Invalid BoxNote content: no type field')
        raise ValueError('Invalid BoxNote content: no type field')
    
    type_tag = content.get('type', '')
    if type_tag == 'paragraph':
        if not ignore_paragraph:
            alignment = 'left'
            marks = content.get('marks', [])
            for mark in marks:
                if mark.get('type', '') == 'alignment':
                    alignment = mark.get('attrs', {}).get('alignment', '')
            contents.append(html_mapper.get_tag_open('paragraph', alignment=alignment))
            parse_content(content.get('content', []), contents, title, workdir)
            contents.append(html_mapper.get_tag_close('paragraph'))
        else:
            parse_content(content.get('content', []), contents, title, workdir)
    elif type_tag == 'text':
        contents.append(html_mapper.get_tag_open('text'))
        contents.append(html_mapper.handle_text_marks(content.get('marks', []), content.get('text', '')))
        contents.append(html_mapper.get_tag_close('text'))
    elif type_tag == 'check_list_item':
        args = {'checked': 'checked' if content['attrs']['checked'] else '', 'x': 'X' if content['attrs']['checked'] else '  '}
        contents.append(html_mapper.get_tag_open('check_list_item', **args))
        parse_content(content.get('content', []), contents, title, workdir, ignore_paragraph=True)
        contents.append(html_mapper.get_tag_close('check_list_item'))
    elif type_tag in ['list_item', 'table_cell', 'call_out_box']:
        contents.append(html_mapper.get_tag_open(type_tag, **content.get('attrs', {})))
        parse_content(content.get('content', []), contents, title, workdir, ignore_paragraph=True)
        contents.append(html_mapper.get_tag_close(type_tag, **content.get('attrs', {})))
    elif type_tag == 'image':
        contents.append(html_mapper.handle_image(content.get('attrs', {}), title, workdir, token, user))
    elif type_tag in ['strong', 'em', 'underline', 'strikethrough', 'ordered_list', 'bullet_list', 'blockquote', 'code_block', 
                      'check_list', 'table', 'table_row', 'heading', 'link', 'font_size', 'font_color', 'horizontal_rule']:
        contents.append(html_mapper.get_tag_open(type_tag, **content.get('attrs', {})))
        parse_content(content.get('content', []), contents, title, workdir)
        contents.append(html_mapper.get_tag_close(type_tag, **content.get('attrs', {})))
    

def convert_boxnote_to_html(input_boxnote_file: Path, box_token: str, output_html_file: Path):
    workdir = Path.cwd()
    with open(input_boxnote_file, 'r', encoding='utf-8') as f:
        content = f.read()
    title = input_boxnote_file.stem
    token = box_token
    user_id = None
    with open(output_html_file, 'w', encoding='utf-8') as f:
        f.write(parse(content, title, workdir, token, user_id))
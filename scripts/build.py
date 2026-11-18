#!/usr/bin/env python3
"""Build editable JSON/Markdown into a portable static site. Python 3.11+."""
import argparse
from datetime import datetime
from email.utils import format_datetime
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
from urllib.parse import urlsplit, urljoin
import xml.etree.ElementTree as ET

TOOL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOL_ROOT / 'vendor'))
import markdown  # Bundled Python-Markdown, with its license in vendor/.

ALLOWED = set('p br hr h1 h2 h3 h4 h5 h6 ul ol li strong em a img blockquote pre code table thead tbody tr th td del s details summary span sub sup'.split())
BLOCKED = set('script style iframe object embed svg math template form'.split())
VOID = {'br', 'hr', 'img'}
RESERVED = {'main','search-dialog','search-input','search-results','search-status','search-title','note-dialog','note-title','note-body','note-category','theme-toggle','theme-dialog','theme-title','email-link'}

def safe_url(value):
    normalized = re.sub(r'[\x00-\x20]', '', value)
    return urlsplit(normalized).scheme.lower() in {'', 'http', 'https', 'mailto'}

class Sanitizer(HTMLParser):
    def __init__(self, namespace, tab_ids):
        super().__init__(convert_charrefs=True)
        self.namespace, self.tab_ids = namespace, tab_ids
        self.parts, self.skip = [], 0
    def handle_starttag(self, tag, attrs):
        if tag in BLOCKED:
            self.skip += 1
            return
        if self.skip or tag not in ALLOWED:
            return
        clean = []
        for key, value in attrs:
            if value is None:
                continue
            if key == 'id' and re.fullmatch(r'[\w-]+', value):
                value = f'{self.namespace}--{value}'
            elif key == 'href' and tag == 'a' and safe_url(value):
                if value.startswith('#') and value[1:] not in self.tab_ids:
                    value = f'#{self.namespace}--{value[1:]}'
            elif key == 'src' and tag == 'img' and safe_url(value) and not value.lower().startswith('mailto:'):
                pass
            elif key in {'alt','title'}:
                pass
            elif key == 'class' and tag in {'code','pre','span'} and re.fullmatch(r'[\w -]+', value):
                pass
            elif key == 'start' and tag == 'ol' and value.isdigit():
                pass
            elif key == 'download' and tag == 'a' and re.fullmatch(r'[\w.-]*', value):
                pass
            else:
                continue
            clean.append(f' {key}="{html.escape(value, quote=True)}"')
        # Preformatted metadata and tables can scroll at narrow widths. Keep
        # their native scroll regions keyboard-reachable without trusting a
        # user-provided tabindex attribute.
        if tag in {'pre', 'table'}:
            clean.append(' tabindex="0"')
        self.parts.append(f'<{tag}{"".join(clean)}>')
    def handle_endtag(self, tag):
        if tag in BLOCKED:
            self.skip = max(0, self.skip - 1)
            return
        if not self.skip and tag in ALLOWED and tag not in VOID:
            self.parts.append(f'</{tag}>')
    def handle_data(self, text):
        if not self.skip:
            self.parts.append(html.escape(text))

class SearchSections(HTMLParser):
    def __init__(self, title, target):
        super().__init__()
        self.current = {'title':title,'target':target,'text':''}
        self.fallback_target = target
        self.sections, self.in_heading = [], False
    def handle_starttag(self, tag, attrs):
        if tag == 'h2':
            if self.current['text'].strip():
                self.sections.append(self.current)
            self.current = {'title':'','target':dict(attrs).get('id',self.fallback_target),'text':''}
            self.in_heading = True
    def handle_endtag(self, tag):
        if tag == 'h2':
            self.in_heading = False
    def handle_data(self, text):
        if self.in_heading:
            self.current['title'] += text
        else:
            self.current['text'] += text + ' '
    def finish(self):
        if self.current['title']:
            self.sections.append(self.current)
        return self.sections

def load_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f'{path.name}: {error}') from error

def source_path(root, value):
    if not isinstance(value, str) or not value:
        raise ValueError('Content file paths must be nonempty strings')
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f'Content path escapes the site folder: {value}')
    if not path.is_file():
        raise ValueError(f'Content file not found: {value}')
    return path

def compile_markdown(root, filename, namespace, title, tab_ids):
    raw = source_path(root, filename).read_text(encoding='utf-8')
    # Fully qualified names work without installed entry-point metadata.
    extensions = [f'markdown.extensions.{name}' for name in ['fenced_code','tables','sane_lists','toc','md_in_html']]
    rendered = markdown.markdown(raw, extensions=extensions)
    sanitizer = Sanitizer(namespace, tab_ids)
    sanitizer.feed(rendered)
    clean = ''.join(sanitizer.parts)
    index = SearchSections(title, namespace)
    index.feed(clean)
    sections = index.finish()
    return clean, sections, ' '.join(item['title'] + ' ' + item['text'] for item in sections)

def validate_id(value, kind='tab'):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*', value):
        raise ValueError(f'Invalid {kind} ID: {value!r}; use lowercase words separated by single hyphens')
    if kind == 'tab' and (value in RESERVED or value.startswith(('tab-','note-'))):
        raise ValueError(f'Reserved tab ID: {value}')

def build(root):
    root = root.resolve()
    site = load_json(root / 'site.json')
    config = load_json(root / 'tabs.json')
    records = config.get('tabs', [])
    if not isinstance(records, list):
        raise ValueError('tabs.json: tabs must be an array')
    seen, enabled = set(), []
    for tab in records:
        validate_id(tab.get('id'))
        if tab['id'] in seen:
            raise ValueError(f'Duplicate tab ID: {tab["id"]}')
        seen.add(tab['id'])
        if not isinstance(tab.get('enabled', True), bool):
            raise ValueError(f'{tab["id"]}: enabled must be true or false')
        if tab.get('enabled', True):
            if not isinstance(tab.get('label'), str) or not tab['label'].strip():
                raise ValueError(f'{tab["id"]}: a label is required')
            enabled.append(tab)
    if not enabled:
        raise ValueError('Enable at least one tab in tabs.json')
    ids = {tab['id'] for tab in enabled}
    compiled, feed_notes = [], []
    for tab in enabled:
        tab_id, title = tab['id'], tab.get('title', tab['label'].capitalize())
        body, search, text = ('', [], '')
        if tab.get('file'):
            body, search, text = compile_markdown(root, tab['file'], tab_id, title, ids)
        notes = []
        if tab.get('notes'):
            note_ids = set()
            entries = load_json(source_path(root, tab['notes']))
            if not isinstance(entries, list):
                raise ValueError(f'{tab_id}: notes index must be an array')
            for note in entries:
                validate_id(note.get('id'), 'note')
                if note['id'] in note_ids:
                    raise ValueError(f'{tab_id}: duplicate note ID: {note["id"]}')
                note_ids.add(note['id'])
                if note.get('enabled', True) is False:
                    continue
                if not isinstance(note.get('title'), str) or not note['title'].strip():
                    raise ValueError(f'{tab_id}/{note["id"]}: a title is required')
                html_body, _, note_text = compile_markdown(root, note['file'], f'note-{tab_id}--{note["id"]}', note['title'], ids)
                compiled_note = {**note, 'html':html_body, 'text':note_text, 'sample':note.get('sample', True)}
                notes.append(compiled_note)
                feed_notes.append((tab_id, compiled_note))
        compiled.append({'id':tab_id,'label':tab['label'],'title':title,'html':body,'text':text,'search':search,'notes':notes})
    default = config.get('default') if config.get('default') in ids else compiled[0]['id']
    data = {**site, 'tabs':compiled, 'defaultTab':default, 'feedURL':'./notes.xml'}
    base = site.get('siteURL', '')
    if urlsplit(base).scheme not in {'https','http'} or not base.endswith('/'):
        raise ValueError('site.json: siteURL must be an HTTP(S) URL ending in /')
    rss = ET.Element('rss', version='2.0')
    channel = ET.SubElement(rss, 'channel')
    for key, value in [('title',site.get('name','')+' — Notes'),('link',base),('description','Notes. Template samples are explicitly labeled.'),('language','en')]:
        ET.SubElement(channel, key).text = value
    for tab_id, note in feed_notes:
        item = ET.SubElement(channel, 'item')
        url = base + f'index.html#note-{tab_id}--{note["id"]}'
        ET.SubElement(item, 'title').text = ('[Sample] ' if note['sample'] else '') + note['title']
        ET.SubElement(item, 'link').text = url
        ET.SubElement(item, 'guid', isPermaLink='true').text = url
        # The input is normalized allowlisted HTML emitted by Sanitizer. Its
        # href/src attributes always use this exact quoted representation.
        feed_html = re.sub(r' (href|src)="([^"]*)"', lambda match: f' {match[1]}="{html.escape(urljoin(base + "index.html", html.unescape(match[2])), quote=True)}"', note['html'])
        ET.SubElement(item, 'description').text = feed_html
        if note.get('date'):
            date = datetime.fromisoformat(note['date'].replace('Z','+00:00'))
            if date.tzinfo is None:
                raise ValueError(f'{note["id"]}: dates need a timezone, e.g. 2026-01-01T12:00:00Z')
            ET.SubElement(item, 'pubDate').text = format_datetime(date)
    title = site.get('title', site.get('name','')+' — Personal site')
    template = (TOOL_ROOT/'templates/index.html').read_text(encoding='utf-8')
    page = template.replace('{{TITLE}}',html.escape(title, quote=True)).replace('{{DESCRIPTION}}',html.escape(site.get('description',''),quote=True))
    page = page.replace('{{FEED_LINK}}','<link rel="alternate" type="application/rss+xml" title="Notes" href="./notes.xml">' if feed_notes else '')
    page = page.replace('{{AGENTMAIL_ICON}}',(TOOL_ROOT/'assets/icons/agentmail.svg').read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory(prefix='.folio-build-',dir=root) as temp:
        staging = Path(temp)
        shutil.copytree(TOOL_ROOT/'assets',staging/'assets',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        if root != TOOL_ROOT and (root/'assets').exists():
            shutil.copytree(root/'assets',staging/'assets',dirs_exist_ok=True)
        (staging/'index.html').write_text(page,encoding='utf-8')
        payload = json.dumps(data,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
        (staging/'site-data.js').write_text('window.SITE = '+payload+';\n',encoding='utf-8')
        ET.indent(rss)
        ET.ElementTree(rss).write(staging/'notes.xml',encoding='utf-8',xml_declaration=True)
        (staging/'.nojekyll').touch()
        output = root/'docs'
        if output.is_symlink():
            raise ValueError('Refusing to replace a symlink at docs/')
        if output.exists():
            shutil.rmtree(output)
        shutil.copytree(staging,output)
    return {'tabs':len(compiled),'notes':len(feed_notes),'default':default,'output':str(root/'docs')}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=TOOL_ROOT)
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.root),indent=2))
    except (ValueError, OSError, TypeError, KeyError) as error:
        print(f'Build failed: {error}',file=sys.stderr)
        sys.exit(1)

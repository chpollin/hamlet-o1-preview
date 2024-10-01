import os
import glob
from lxml import etree
import json

# Define the data folder containing TEI XML files
data_folder = 'data'

# Find all TEI XML files in the data folder
xml_files = glob.glob(os.path.join(data_folder, '*.xml'))

# Initialize a list to hold all the extracted information
texts_data = []

for xml_file in xml_files:
    # Get edition identifier from the file name
    edition_id = os.path.splitext(os.path.basename(xml_file))[0]
    
    # Parse the TEI XML file
    parser = etree.XMLParser(ns_clean=True, recover=True)
    tree = etree.parse(xml_file, parser)
    root = tree.getroot()
    
    # Define namespaces
    namespaces = {'tei': 'http://www.tei-c.org/ns/1.0'}
    
    # Get metadata: title, author, date
    title_elem = root.find('.//tei:titlePart[@type="main"]', namespaces)
    title_text = ''.join(title_elem.itertext()) if title_elem is not None else ''
    
    date_elem = root.find('.//tei:docDate', namespaces)
    date_text = ''.join(date_elem.itertext()) if date_elem is not None else ''
    
    author_elem = root.find('.//tei:docAuthor', namespaces)
    author_text = ''.join(author_elem.itertext()) if author_elem is not None else ''
    
    # Traverse acts and scenes
    acts = root.findall('.//tei:div1[@type="act"]', namespaces)
    for act in acts:
        act_number = act.get('n')
        scenes = act.findall('.//tei:div2[@type="scene"]', namespaces)
        for scene in scenes:
            scene_number = scene.get('n')
            # Get all speeches in the scene
            speeches = scene.findall('.//tei:sp', namespaces)
            for sp in speeches:
                who = sp.get('who')
                speaker_name = who.strip('#') if who else ''
                # Get all the lines spoken
                lines = sp.findall('.//tei:l', namespaces)
                for line in lines:
                    # Preserve original orthography and punctuation
                    line_text = ''.join(line.itertext())
                    line_number = line.get('n')  # Get line number if available
                    texts_data.append({
                        'edition': edition_id,
                        'title': title_text,
                        'author': author_text,
                        'date': date_text,
                        'act': act_number,
                        'scene': scene_number,
                        'speaker': speaker_name,
                        'line_number': line_number,
                        'text': line_text
                    })

# Save the extracted data to a JSON file
with open('texts_data.json', 'w', encoding='utf-8') as f:
    json.dump(texts_data, f, ensure_ascii=False, indent=4)

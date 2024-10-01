import os
import glob
from lxml import etree
import json
from collections import defaultdict

# Define the data folder containing TEI XML files
data_folder = 'data'

# Find all TEI XML files in the data folder
xml_files = glob.glob(os.path.join(data_folder, '*.xml'))

# Initialize data structures
texts_data = []
interaction_counts = defaultdict(lambda: defaultdict(int))  # {edition: {character_pair: count}}

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
            # Collect all characters present in the scene
            characters_in_scene = set()
            for sp in speeches:
                who = sp.get('who')
                speaker_name = who.strip('#') if who else ''
                characters_in_scene.add(speaker_name)
                # Get all the lines spoken
                lines = sp.findall('.//tei:l', namespaces)
                for line in lines:
                    line_text = ''.join(line.itertext())
                    line_number = line.get('n')
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
            # Update interaction counts between characters in this scene
            for character in characters_in_scene:
                for other in characters_in_scene:
                    if other != character:
                        # Create a sorted tuple to avoid duplicate pairs
                        pair = tuple(sorted([character, other]))
                        interaction_counts[edition_id][pair] += 1

# Save the extracted text data to a JSON file
with open('texts_data.json', 'w', encoding='utf-8') as f:
    json.dump(texts_data, f, ensure_ascii=False, indent=4)

# Save the interaction counts to a JSON file
with open('interaction_data.json', 'w', encoding='utf-8') as f:
    interaction_data_output = {}
    for edition, counts in interaction_counts.items():
        edition_data = {}
        for pair, count in counts.items():
            pair_key = f"{pair[0]}-{pair[1]}"
            edition_data[pair_key] = count
        interaction_data_output[edition] = edition_data
    json.dump(interaction_data_output, f, ensure_ascii=False, indent=4)

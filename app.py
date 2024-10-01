from flask import Flask, render_template, request, redirect, url_for, flash, abort
import json
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from collections import OrderedDict
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a secure key

# Set up the database for annotations
engine = create_engine('sqlite:///annotations.db')
db_session = scoped_session(sessionmaker(bind=engine))
Base = declarative_base()

# Define the Annotation model
class Annotation(Base):
    __tablename__ = 'annotations'
    id = Column(Integer, primary_key=True)
    edition = Column(String(100))
    act = Column(String(10))
    scene = Column(String(10))
    speaker = Column(String(100))
    line_number = Column(String(10))
    text = Column(Text)

Base.metadata.create_all(bind=engine)

# Load the data from the JSON file
with open('texts_data.json', 'r', encoding='utf-8') as f:
    texts_data = json.load(f)

# Organize the data by edition
editions = {}
for entry in texts_data:
    edition = entry['edition']
    if edition not in editions:
        editions[edition] = []
    editions[edition].append(entry)

# Update the context processor to include Annotation
@app.context_processor
def inject_db_session():
    return dict(db_session=db_session, Annotation=Annotation)

@app.route('/')
def index():
    return render_template('index.html', editions=editions, title="Home")

@app.route('/edition/<edition_id>')
def view_edition(edition_id):
    edition_data = editions.get(edition_id)
    if not edition_data:
        abort(404)
    
    # Organize data by act and scene
    acts = OrderedDict()
    for entry in edition_data:
        act_num = entry.get('act') or 'Unknown Act'
        scene_num = entry.get('scene') or 'Unknown Scene'
        if act_num not in acts:
            acts[act_num] = OrderedDict()
        if scene_num not in acts[act_num]:
            acts[act_num][scene_num] = []
        acts[act_num][scene_num].append(entry)
    
    return render_template(
        'edition.html',
        edition_id=edition_id,
        acts=acts,
        title=f"Edition {edition_id}"
    )

@app.route('/compare', methods=['GET', 'POST'])
def compare_editions():
    if request.method == 'POST':
        edition1 = request.form.get('edition1')
        edition2 = request.form.get('edition2')
        data1 = editions.get(edition1, [])
        data2 = editions.get(edition2, [])
        
        # Organize data by act, scene, speaker, and line number for alignment
        def organize_data(data):
            organized = {}
            for entry in data:
                key = (entry.get('act'), entry.get('scene'), entry.get('speaker'), entry.get('line_number'))
                organized[key] = entry
            return organized
        
        data1_organized = organize_data(data1)
        data2_organized = organize_data(data2)
        
        # Get all keys for alignment
        all_keys = sorted(set(data1_organized.keys()) | set(data2_organized.keys()))
        
        aligned_data = []
        for key in all_keys:
            e1 = data1_organized.get(key)
            e2 = data2_organized.get(key)
            aligned_data.append((e1, e2))
        
        return render_template('compare.html', edition1=edition1, edition2=edition2, aligned_data=aligned_data, title="Compare Editions")
    else:
        return render_template('compare_select.html', editions=editions, title="Compare Editions")

@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        query = request.form.get('query', '').lower()
        edition = request.form.get('edition')
        speaker = request.form.get('speaker')
        act = request.form.get('act')
        scene = request.form.get('scene')
        results = []
        for entry in texts_data:
            if query in entry['text'].lower():
                if (not edition or entry['edition'] == edition) and \
                   (not speaker or entry['speaker'] == speaker) and \
                   (not act or entry['act'] == act) and \
                   (not scene or entry['scene'] == scene):
                    results.append(entry)
        return render_template('search.html', query=query, results=results, editions=editions.keys(), title=f"Search Results for '{query}'")
    else:
        return render_template('search_form.html', editions=editions.keys(), title="Advanced Search")

with open('interaction_data.json', 'r', encoding='utf-8') as f:
    interaction_data = json.load(f)

@app.route('/interactions')
def interactions():
    # List all available editions
    edition_list = list(interaction_data.keys())
    return render_template('interactions_select.html', editions=edition_list, title="Character Interactions")

@app.route('/interactions/<edition_id>')
def view_interactions(edition_id):
    interactions = interaction_data.get(edition_id)
    if not interactions:
        abort(404)
    return render_template('interactions.html', edition_id=edition_id, interactions=interactions, title=f"Interactions in {edition_id}")

@app.route('/annotate', methods=['POST'])
def annotate():
    edition = request.form.get('edition')
    act = request.form.get('act')
    scene = request.form.get('scene')
    speaker = request.form.get('speaker')
    line_number = request.form.get('line_number')
    annotation_text = request.form.get('annotation_text')
    if annotation_text:
        annotation = Annotation(
            edition=edition,
            act=act,
            scene=scene,
            speaker=speaker,
            line_number=line_number,
            text=annotation_text
        )
        db_session.add(annotation)
        db_session.commit()
        flash('Annotation added successfully.')
    else:
        flash('Annotation text cannot be empty.')
    return redirect(url_for('view_edition', edition_id=edition))

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html', title="Page Not Found"), 404

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

if __name__ == '__main__':
    app.run(debug=True)

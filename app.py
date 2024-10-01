from flask import Flask, render_template, request, redirect, url_for, flash, abort
import json
import os
from collections import defaultdict, OrderedDict, Counter
from sqlalchemy import create_engine, Column, Integer, String, Text, Sequence
from sqlalchemy.orm import scoped_session, sessionmaker, declarative_base
from sqlalchemy.orm import declarative_base
from sqlalchemy.exc import ProgrammingError, IntegrityError
from sqlalchemy import inspect, text
import difflib  # For textual variants visualization
from flask import Flask
from whitenoise import WhiteNoise

def init_db():
    inspector = inspect(engine)
    
    if not inspector.has_table("annotations"):
        with engine.connect() as connection:
            try:
                # Check if the sequence exists
                connection.execute(text("SELECT EXISTS (SELECT 1 FROM pg_sequences WHERE sequencename = 'annotations_id_seq');"))
                seq_exists = connection.fetchone()[0]
                
                if seq_exists:
                    # If sequence exists, drop it
                    connection.execute(text("DROP SEQUENCE annotations_id_seq;"))
                
                # Create the table (this will also create the sequence)
                Base.metadata.create_all(bind=engine)
                print("Database tables and sequences created.")
            except (ProgrammingError, IntegrityError) as e:
                print(f"An error occurred during database initialization: {e}")
                connection.rollback()
    else:
        print("Tables already exist.")

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dimHamlet!74916')  # Ensure you're using environment variables
app.wsgi_app = WhiteNoise(app.wsgi_app, root='static/')

DATABASE_URL = os.environ.get('DATABASE_URL')

# Fix the database URL scheme if necessary
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Add client_encoding parameter
if '?' in DATABASE_URL:
    DATABASE_URL += "&client_encoding=utf8"
else:
    DATABASE_URL += "?client_encoding=utf8"

# Set up the database for annotations
engine = create_engine(DATABASE_URL)
db_session = scoped_session(sessionmaker(bind=engine))

Base = declarative_base()

class Annotation(Base):
    __tablename__ = 'annotations'
    id = Column(Integer, primary_key=True)  # PostgreSQL will use SERIAL by default
    edition = Column(String(100))
    act = Column(String(10))
    scene = Column(String(10))
    speaker = Column(String(100))
    line_number = Column(String(10))
    text = Column(Text)

Base.metadata.create_all(bind=engine)

# Initialize the database
try:
    init_db()
except Exception as e:
    print(f"An error occurred during database initialization: {e}")

try:
    with open('texts_data.json', 'r', encoding='utf-8') as f:
        texts_data = json.load(f)

    with open('interaction_data.json', 'r', encoding='utf-8') as f:
        interaction_data_raw = json.load(f)
except FileNotFoundError as e:
    print(f"Error: JSON file not found. {e}")
    texts_data = []
    interaction_data_raw = {}
except json.JSONDecodeError as e:
    print(f"Error: Invalid JSON in data files. {e}")
    texts_data = []
    interaction_data_raw = {}

# Process the interaction data into a suitable format
interaction_data = {}
for edition, pairs in interaction_data_raw.items():
    interactions = []
    node_set = set()
    node_degree = defaultdict(int)
    for pair_str, count in pairs.items():
        character1, character2 = pair_str.split('-')
        node_set.update([character1, character2])
        interactions.append({
            'source': character1,
            'target': character2,
            'value': count  # Edge weight
        })
        node_degree[character1] += count
        node_degree[character2] += count
    nodes = [{'id': character, 'degree': node_degree[character]} for character in node_set]
    interaction_data[edition] = {'nodes': nodes, 'links': interactions}

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

# Updated compare_editions route with textual variants visualization
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
            diff = None
            if e1 and e2:
                diff = difflib.HtmlDiff().make_table(
                    [e1['text']], [e2['text']],
                    fromdesc=edition1, todesc=edition2,
                    context=True, numlines=0
                )
            aligned_data.append((e1, e2, diff))
        
        return render_template('compare.html', edition1=edition1, edition2=edition2, aligned_data=aligned_data, title="Compare Editions")
    else:
        return render_template('compare_select.html', editions=editions, title="Compare Editions")

@app.route('/interactions')
def interactions():
    # List all available editions
    edition_list = list(interaction_data.keys())
    return render_template('interactions_select.html', editions=edition_list, title="Character Interactions")

@app.route('/interactions/<edition_id>')
def view_interactions(edition_id):
    data = interaction_data.get(edition_id)
    if not data:
        abort(404)
    return render_template('interactions.html', edition_id=edition_id, data=data, title=f"Interactions in {edition_id}")

@app.route('/compare_interactions', methods=['GET', 'POST'])
def compare_interactions():
    if request.method == 'POST':
        edition1 = request.form.get('edition1')
        edition2 = request.form.get('edition2')
        data1 = interaction_data.get(edition1)
        data2 = interaction_data.get(edition2)
        if not data1 or not data2:
            abort(404)
        
        # Prepare merged data for visualization
        # Merge nodes
        nodes_dict = {}
        for node in data1['nodes']:
            nodes_dict[node['id']] = {'id': node['id']}
        for node in data2['nodes']:
            nodes_dict[node['id']] = {'id': node['id']}
        nodes = list(nodes_dict.values())
        
        # Merge links
        link_map = {}
        for link in data1['links']:
            key = (link['source'], link['target'])
            link_map[key] = {
                'source': link['source'],
                'target': link['target'],
                'value1': link['value'],
                'value2': 0,
                'editions': [edition1]
            }
        for link in data2['links']:
            key = (link['source'], link['target'])
            if key in link_map:
                link_map[key]['value2'] = link['value']
                link_map[key]['editions'].append(edition2)
            else:
                link_map[key] = {
                    'source': link['source'],
                    'target': link['target'],
                    'value1': 0,
                    'value2': link['value'],
                    'editions': [edition2]
                }
        links = list(link_map.values())
        
        return render_template(
            'compare_interactions.html',
            edition1=edition1,
            edition2=edition2,
            nodes=nodes,
            links=links,
            title=f"Compare Character Interactions: {edition1} vs {edition2}"
        )
    else:
        edition_list = list(interaction_data.keys())
        return render_template('compare_interactions_select.html', editions=edition_list, title="Compare Character Interactions")

# New route for Word Frequency Analysis
@app.route('/word_frequency', methods=['GET', 'POST'])
def word_frequency():
    if request.method == 'POST':
        edition = request.form.get('edition')
        num_words = int(request.form.get('num_words', 20))
        # Get text data for the selected edition
        data = editions.get(edition)
        if not data:
            abort(404)
        # Concatenate all text entries
        full_text = ' '.join(entry['text'] for entry in data)
        # Tokenize and count words
        words = [word.lower() for word in full_text.split()]
        word_counts = Counter(words)
        most_common = word_counts.most_common(num_words)
        # Prepare data for visualization
        labels, values = zip(*most_common)
        return render_template(
            'word_frequency.html',
            edition=edition,
            labels=labels,
            values=values,
            num_words=num_words,
            title=f"Word Frequency in {edition}"
        )
    else:
        return render_template('word_frequency_select.html', editions=editions.keys(), title="Word Frequency Analysis")

# New route for Concordance (Keyword in Context)
@app.route('/concordance', methods=['GET', 'POST'])
def concordance():
    if request.method == 'POST':
        keyword = request.form.get('keyword', '').lower()
        edition = request.form.get('edition')
        window_size = int(request.form.get('window_size', 5))
        results = []
        data = editions.get(edition) if edition else texts_data
        for entry in data:
            text = entry['text']
            words = text.split()
            for i, word in enumerate(words):
                if keyword == word.lower():
                    start = max(i - window_size, 0)
                    end = min(i + window_size + 1, len(words))
                    context_words = words[start:end]
                    # Highlight the keyword
                    context_words[i - start] = f"<strong>{context_words[i - start]}</strong>"
                    context = ' '.join(context_words)
                    results.append({
                        'edition': entry['edition'],
                        'speaker': entry['speaker'],
                        'act': entry['act'],
                        'scene': entry['scene'],
                        'context': context,
                        'keyword': keyword
                    })
        return render_template(
            'concordance.html',
            keyword=keyword,
            results=results,
            editions=editions.keys(),
            title=f"Concordance for '{keyword}'"
        )
    else:
        return render_template('concordance_form.html', editions=editions.keys(), title="Concordance Search")

# New route for Lexical Dispersion Plot
@app.route('/dispersion', methods=['GET', 'POST'])
def dispersion():
    if request.method == 'POST':
        keyword = request.form.get('keyword', '').lower()
        edition = request.form.get('edition')
        data = editions.get(edition)
        if not data:
            abort(404)
        # Prepare data for dispersion plot
        word_positions = []
        total_words = 0
        for entry in data:
            text = entry['text']
            words = text.split()
            for word in words:
                if word.lower() == keyword:
                    word_positions.append(total_words)
                total_words += 1
        return render_template(
            'dispersion.html',
            keyword=keyword,
            positions=word_positions,
            total_words=total_words,
            edition=edition,
            title=f"Lexical Dispersion of '{keyword}' in {edition}"
        )
    else:
        return render_template('dispersion_form.html', editions=editions.keys(), title="Lexical Dispersion Plot")

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

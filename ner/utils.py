import spacy
from django.conf import settings


def get_doc_result(doc):
    teams = [d.text for d in doc.ents if d.label_ == 'Team']
    players = [d.text for d in doc.ents if d.label_ == 'Player']
    minutes = [d.text for d in doc.ents if d.label_ == 'Minute']
    if len(teams) == 2:
        home_team = teams[0]
        away_team = teams[1]
    elif len(teams) == 1:
        home_team = teams[0]
        away_team = None
    elif len(teams) > 2:
        home_team = teams[0]
        away_team = teams[1]
    else:
        return None, None, None, None
    player = players[0] if len(players) == 1 else None
    minute = minutes[0] if len(minutes) == 1 else None
    return home_team, away_team, player, minute


def extract_names_from_title_ner(title):
    nlp_model = spacy.load(settings.NER_MODEL_FOLDER)
    doc = nlp_model(title)
    return get_doc_result(doc)

import os
import string
from collections import Counter
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
import seaborn as sns
import torch
from docx import Document
from nltk.corpus import stopwords
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from transformers import (
    BertTokenizer, BertModel,
    RobertaTokenizer, RobertaForSequenceClassification,
    pipeline
)
import nltk

# =============================
# Download NLTK Data
# =============================
nltk.download('punkt')
nltk.download('stopwords')

# =============================
# Load Pretrained Models
# =============================
bert_tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
bert_model = BertModel.from_pretrained('bert-base-uncased')

roberta_tokenizer = RobertaTokenizer.from_pretrained('SamLowe/roberta-base-go_emotions')
roberta_model = RobertaForSequenceClassification.from_pretrained('SamLowe/roberta-base-go_emotions')
sentiment_analyzer = pipeline("text-classification", model=roberta_model, tokenizer=roberta_tokenizer)

# =============================
# Text pre-processing Functions
# =============================
def preprocess_text(text):
    stop_words = set(stopwords.words('english'))
    text = text.lower()
    text = ''.join([char for char in text if char not in string.punctuation])
    return ' '.join([word for word in text.split() if word not in stop_words])

def encode(texts, tokenizer, model):
    encoded_input = tokenizer(texts, padding=True, truncation=True, return_tensors='pt', max_length=128)
    with torch.no_grad():
        model_output = model(**encoded_input)
    return model_output.last_hidden_state[:, 0, :].detach().cpu().numpy()

# =============================
# One-Word Topic Extraction from .docx
# =============================
def extract_one_word_topics_from_docx(doc_path, num_topics=8):
    doc = Document(doc_path)
    raw_text = '\n'.join([para.text for para in doc.paragraphs if para.text.strip()])

    stop_words = set(stopwords.words('english'))
    raw_text = raw_text.lower()
    raw_text = ''.join([ch for ch in raw_text if ch not in string.punctuation])
    tokens = nltk.word_tokenize(raw_text)
    tokens = [word for word in tokens if word.isalpha() and word not in stop_words]

    if not tokens:
        return []

    processed_text = ' '.join(tokens)
    vectorizer = TfidfVectorizer(max_features=500)
    tfidf_matrix = vectorizer.fit_transform([processed_text])
    vocab = vectorizer.get_feature_names_out()

    if len(vocab) < num_topics:
        return vocab.tolist()

    kmeans = KMeans(n_clusters=num_topics, random_state=42, n_init='auto')
    kmeans.fit(tfidf_matrix.T)

    topics = []
    bad_words = {"able", "good", "bad", "responsible", "important", "many", "every", "more", "most"}
    for i in range(num_topics):
        cluster_indices = np.where(kmeans.labels_ == i)[0]
        if cluster_indices.size > 0:
            cluster_scores = tfidf_matrix.T[cluster_indices].toarray().sum(axis=1)
            sorted_indices = cluster_indices[np.argsort(-cluster_scores)]
            for idx in sorted_indices:
                word = vocab[idx]
                if len(word) > 3 and word not in bad_words:
                    topics.append(word)
                    break
            else:
                topics.append(vocab[sorted_indices[0]])
    return topics

# =============================
# Loading and Processing Topics
# =============================
document_paths = [f'/Users/kinjalsingh/Downloads/ssdoc{i}.docx' for i in range(1, 9)]
extracted_topics = [extract_one_word_topics_from_docx(doc) for doc in document_paths if os.path.exists(doc)]
flat_extracted_topics = [topic for sublist in extracted_topics for topic in sublist]
preprocessed_topics = [preprocess_text(topic) for topic in flat_extracted_topics]

if not extracted_topics:
    raise ValueError("No topics were extracted. Check document formatting and paths.")

# =============================
# Load and Preprocess Transcriptions
# =============================
with open('/Users/kinjalsingh/Downloads/blue_group.txt', 'r') as f: 
    original_sentences = [line.strip() for line in f.readlines()]
    preprocessed_sentences = [preprocess_text(line) for line in original_sentences]

# =============================
# Embeddings and Similarity scores
# =============================
topic_embeddings = encode(preprocessed_topics, bert_tokenizer, bert_model)
transcription_embeddings = encode(preprocessed_sentences, bert_tokenizer, bert_model)
similarity_matrix = cosine_similarity(transcription_embeddings, topic_embeddings)

# ==============================================================
# Analyze Sentiment & Similarity and appending to 'result' array
# ==============================================================
SIMILARITY_THRESHOLD = 0.55
SENTIMENT_THRESHOLD = 0.55

results = []
for i, similarities in enumerate(similarity_matrix):
    max_index = np.argmax(similarities)
    similarity_score = similarities[max_index]

    sentiment_result = sentiment_analyzer(original_sentences[i])
    sentiment_label = sentiment_result[0]['label']
    sentiment_score = sentiment_result[0]['score']

    result = {
        'original_sentence': original_sentences[i],
        'preprocessed_sentence': preprocessed_sentences[i],
        'similarity_score': similarity_score,
        'sentiment_score': sentiment_score,
        'most_similar_topic': flat_extracted_topics[max_index] if similarity_score >= SIMILARITY_THRESHOLD else "Unknown",
        'sentiment': sentiment_label if sentiment_score >= SENTIMENT_THRESHOLD else "Unknown"
    }

    results.append(result)

# =============================
# Visualizations
# =============================
df = pd.DataFrame(results)
start_time = datetime.now()
df['date'] = [start_time + timedelta(minutes=i) for i in range(len(df))]
df['date'] = pd.to_datetime(df['date'])

# =============================
# Line Plot, Sentiment over Time
# =============================
fig = px.line(
    df,
    x='date',
    y='sentiment_score',
    color='most_similar_topic',
    title='Sentiment Score over Time by Topic'
)
fig.show()

# =============================
# Bar Plot, Sentiment Distribution
# =============================
sentiment_counts = Counter(df['sentiment'])
plt.bar(sentiment_counts.keys(), sentiment_counts.values())
plt.title('Distribution of Sentiments')
plt.ylabel('Count')
plt.show()

# =============================
# Stacked Bar, Sentiment by Topic
# =============================
topic_sentiment_counts = df.groupby(['most_similar_topic', 'sentiment']).size().unstack().fillna(0)
long_df = topic_sentiment_counts.reset_index().melt(id_vars=['most_similar_topic'], var_name='sentiment', value_name='count')

fig = px.bar(
    long_df,
    x='most_similar_topic',
    y='count',
    color='sentiment',
    title='Sentiment Distribution per Topic',
    labels={'most_similar_topic': 'Topics', 'count': 'Count'},
    barmode='stack'
)
fig.update_layout(
    xaxis_title='Topics',
    yaxis_title='Count',
    xaxis={'categoryorder': 'total descending'},
    legend_title_text='Sentiment'
)
fig.update_xaxes(tickangle=45)
fig.show()

# =============================
# Heatmap, Avg Similarity Score by Topic & Sentiment
# =============================
pivot_table = df.pivot_table(index='most_similar_topic', columns='sentiment', values='similarity_score', aggfunc='mean', fill_value=0)

fig = px.imshow(
    pivot_table,
    labels=dict(x="Sentiment", y="Topic", color="Similarity Score"),
    x=pivot_table.columns,
    y=pivot_table.index,
    aspect="auto",
    text_auto=True,
    color_continuous_scale='RdBu'
)
fig.update_layout(title='Average Similarity Score by Topic and Sentiment', xaxis_nticks=36)
fig.show()

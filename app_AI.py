import os
import re
import ssl
import requests
import pandas as pd
import cloudscraper
from flask import Flask, request, render_template, redirect, url_for, send_file, jsonify, session
from werkzeug.utils import secure_filename
from Bio import Entrez
from io import BytesIO
from xml.etree import ElementTree as ET
from http.client import IncompleteRead
from bs4 import BeautifulSoup
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
import subprocess
from requests.exceptions import RequestException
import urllib.request
import urllib.error
import http.client
import nltk

# Attempt to fix the CERTIFICATE_VERIFY_FAILED error
try:
	ssl._create_default_https_context = ssl._create_unverified_context
	nltk.download('punkt')
	print("Successfully downloaded 'punkt' tokenizer models.")
except Exception as e:
	print(f"An error occurred: {e}")

# Set your email for NCBI Entrez
Entrez.email = "your_email@example.com"

# Create an unverified SSL context
ssl_context = ssl._create_unverified_context()

# Create a custom HTTPS handler that ignores SSL certificate errors
class HTTPSHandlerIgnoreSSL(urllib.request.HTTPSHandler):
	def __init__(self, context=None, check_hostname=None):
		super().__init__(context=context)
		self.check_hostname = check_hostname

	def https_open(self, req):
		return self.do_open(self.getConnection, req)

	def getConnection(self, host, **kwargs):
		return http.client.HTTPSConnection(host, context=ssl_context, **kwargs)

# Patch Entrez to use the custom handler
def patched_urlopen(request):
	opener = urllib.request.build_opener(HTTPSHandlerIgnoreSSL(context=ssl_context))
	return opener.open(request)

Entrez.urlopen = patched_urlopen

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Directory to save uploaded files
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def search_pubmed(query):
	handle = Entrez.esearch(db="pubmed", term=query, retmax=1000000, usehistory="y")
	record = Entrez.read(handle)
	handle.close()
	return record["IdList"], record["Count"]

def fetch_pubmed_details(id_list, retries=5):
	ids = ",".join(id_list)
	attempt = 0
	while attempt < retries:
		try:
			handle = Entrez.efetch(db="pubmed", id=ids, rettype="xml", retmode="xml")
			records = handle.read()
			handle.close()
			return records
		except IncompleteRead as e:
			attempt += 1
			if attempt >= retries:
				raise e

def parse_pubmed_xml(xml_data):
	root = ET.fromstring(xml_data)
	articles = []
	for article in root.findall(".//PubmedArticle"):
		title = article.findtext(".//ArticleTitle", "")
		year = article.findtext(".//PubDate/Year", "")
		month = article.findtext(".//PubDate/Month", "")
		pub_date = f"{month} {year}".strip() if month or year else ""
		abstract = article.findtext(".//AbstractText", "")
		pmid = article.findtext(".//MedlineCitation/PMID", "")
		journal = article.findtext(".//Journal/Title", "")
		issn = article.findtext(".//Journal/ISSN", "")
		doi = article.findtext(".//ArticleId[@IdType='doi']", "")

		authors = "; ".join(
			[
				f"{author.findtext('LastName', '')}, {author.findtext('ForeName', '')}".strip()
				for author in article.findall(".//AuthorList/Author")
			]
		)

		affiliations = "; ".join(
			[aff.findtext(".//Affiliation", "") for aff in article.findall(".//AuthorList/Author/AffiliationInfo")]
		)

		# Limit cell content to 6000 characters
		title = title[:6000]
		abstract = abstract[:6000]
		authors = authors[:6000]
		affiliations = affiliations[:6000]

		article_data = {
			"title": title,
			"pub_date": pub_date,
			"abstract": abstract,
			"authors": authors,
			"journal": journal,
			"issn": issn,
			"doi": doi,
			"pmid": pmid,
			"affiliations": affiliations,
			"link": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}",
			"label": ""  # Placeholder for label
		}
		articles.append(article_data)

	return articles

def fetch_full_text_from_doi(doi):
	url = f"https://doi.org/{doi}"
	scraper = cloudscraper.create_scraper()
	try:
		response = scraper.get(url)
		response.raise_for_status()
	except RequestException as e:
		print(f"Error fetching full text for DOI {doi}: {e}")
		return None
	return response.text

def summarize_text(text):
	parser = PlaintextParser.from_string(text, Tokenizer("english"))
	summarizer = LsaSummarizer()
	summary = summarizer(parser.document, 4)  # Summarize to 4 sentences
	return ' '.join([str(sentence) for sentence in summary])

def extract_sections_and_tables(full_text):
	soup = BeautifulSoup(full_text, 'html.parser')
	sections = {
		"methods": summarize_text(soup.find("section", {"type": "methods"}).get_text()) if soup.find("section", {"type": "methods"}) 
			else summarize_text(soup.find("section", {"type": "methodology"}).get_text()) if soup.find("section", {"type": "methodology"}) 
			else summarize_text(soup.find("section", {"type": "method"}).get_text()) if soup.find("section", {"type": "method"})
			else summarize_text(soup.find("section", {"type": "materials and methods"}).get_text()) if soup.find("section", {"type": "materials and methods"})
			else summarize_text(soup.find("section", {"data-type": "methods"}).get_text()) if soup.find("section", {"data-type": "methods"}) 
			else summarize_text(soup.find("section", {"data-type": "methodology"}).get_text()) if soup.find("section", {"data-type": "methodology"}) 
			else summarize_text(soup.find("section", {"data-type": "method"}).get_text()) if soup.find("section", {"data-type": "method"})
			else summarize_text(soup.find("section", {"data-type": "materials and methods"}).get_text()) if soup.find("section", {"data-type": "materials and methods"})
			else summarize_text(soup.find("section", {"data-title": "Materials and methods"}).get_text()) if soup.find("section", {"data-title": "Materials and methods"})
			else summarize_text(soup.find("section", {"data-title": "Methods"}).get_text()) if soup.find("section", {"data-title": "Methods"})
			else summarize_text(soup.find("section", {"type": "methods"}).get_text()) if soup.find("section", {"type": "methods"})
			else summarize_text(soup.find("section", {"type": "Methods"}).get_text()) if soup.find("section", {"type": "Methods"})
			else "None available",
		"results": summarize_text(soup.find("section", {"type": "results"}).get_text()) if soup.find("section", {"type": "results"}) 
			else summarize_text(soup.find("section", {"data-type": "results"}).get_text()) if soup.find("section", {"data-type": "results"})
			else summarize_text(soup.find("section", {"data-title": "Results"}).get_text()) if soup.find("section", {"data-title": "Results"})
			else summarize_text(soup.find("section", {"type": "results"}).get_text()) if soup.find("section", {"type": "results"})
			else summarize_text(soup.find("section", {"type": "Results"}).get_text()) if soup.find("section", {"type": "Results"})
			else "None available",
		"discussion": summarize_text(soup.find("section", {"type": "discussion"}).get_text()) if soup.find("section", {"type": "discussion"}) 
			else summarize_text(soup.find("section", {"data-title": "Discussion"}).get_text()) if soup.find("section", {"data-title": "Discussion"})
			else summarize_text(soup.find("section", {"data-type": "discussion"}).get_text()) if soup.find("section", {"data-type": "discussion"})
			else summarize_text(soup.find("section", {"data-section-name": "DISCUSSION"}).get_text()) if soup.find("section", {"data-section-name": "DISCUSSION"})
			else summarize_text(soup.find("section", {"type": "discussion"}).get_text()) if soup.find("section", {"type": "discussion"})
			else summarize_text(soup.find("section", {"type": "Discussion"}).get_text()) if soup.find("section", {"type": "Discussion"})
			else "None available",
		"conclusion": summarize_text(soup.find("section", {"type": "conclusion"}).get_text()) if soup.find("section", {"type": "conclusion"}) 
			else summarize_text(soup.find("section", {"data-title": "Conclusion"}).get_text()) if soup.find("section", {"data-title": "Conclusion"})
			else summarize_text(soup.find("section", {"data-title": "Conclusions"}).get_text()) if soup.find("section", {"data-title": "Conclusions"})
			else summarize_text(soup.find("section", {"data-type": "conclusion"}).get_text()) if soup.find("section", {"data-type": "conclusion"})
			else summarize_text(soup.find("section", {"type": "conclusion"}).get_text()) if soup.find("section", {"type": "conclusion"})
			else summarize_text(soup.find("section", {"type": "Conclusion"}).get_text()) if soup.find("section", {"type": "Conclusion"})
			else "None available",
	}
	tables = [str(table) for table in soup.find_all("table")]
	return sections, tables

def create_pdf_buffer(articles, num_articles, query):
	pdf_buffer = BytesIO()
	doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
	styles = getSampleStyleSheet()
	elements = []

	elements.append(Paragraph(f"Top {num_articles} Articles for Query: {query}", styles['Title']))
	elements.append(Spacer(1, 12))

	for article in articles[:num_articles]:
		elements.append(Paragraph(f"Title: {article.get('title', '')}", styles['Heading2']))
		elements.append(Paragraph(f"Publication Date: {article.get('pub_date', '')}", styles['BodyText']))
		elements.append(Paragraph(f"Authors: {article.get('authors', '')}", styles['BodyText']))
		elements.append(Paragraph(f"Journal: {article.get('journal', '')}", styles['BodyText']))
		elements.append(Paragraph(f"Abstract: {article.get('abstract', '')}", styles['BodyText']))
		elements.append(Paragraph(f"DOI: {article.get('doi', '')}", styles['BodyText']))
		elements.append(Paragraph(f"PMID: {article.get('pmid', '')}", styles['BodyText']))
		elements.append(Spacer(1, 12))

		article_link = f"https://doi.org/{article.get('doi', '')}"
		elements.append(Paragraph(f"Full Article: <a href='{article_link}'>{article_link}</a>", styles['BodyText']))

		if article.get("doi"):
			full_text = fetch_full_text_from_doi(article["doi"])
			if full_text:
				sections, tables = extract_sections_and_tables(full_text)
				elements.append(Paragraph("Methods:", styles['Heading3']))
				elements.append(Paragraph(sections.get("methods", "None available"), styles['BodyText']))
				elements.append(Paragraph("Results:", styles['Heading3']))
				elements.append(Paragraph(sections.get("results", "None available"), styles['BodyText']))
				elements.append(Paragraph("Discussion:", styles['Heading3']))
				elements.append(Paragraph(sections.get("discussion", "None available"), styles['BodyText']))
				elements.append(Paragraph("Conclusion:", styles['Heading3']))
				elements.append(Paragraph(sections.get("conclusion", "None available"), styles['BodyText']))
				elements.append(Spacer(1, 12))

				for table_html in tables:
					table = parse_html_table(table_html)
					table_data = [list(map(str, row)) for row in table]
					pdf_table = Table(table_data)
					pdf_table.setStyle(TableStyle([
						('BACKGROUND', (0, 0), (-1, 0), colors.grey),
						('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
						('ALIGN', (0, 0), (-1, -1), 'CENTER'),
						('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
						('FONTSIZE', (0, 0), (-1, -1), 8),
						('BOTTOMPADDING', (0, 0), (-1, 0), 12),
						('BACKGROUND', (0, 1), (-1, -1), colors.beige),
						('GRID', (0, 0), (-1, -1), 1, colors.black),
					]))
					elements.append(pdf_table)
					elements.append(Spacer(1, 12))
			else:
				elements.append(Paragraph("Methods: None available", styles['BodyText']))
				elements.append(Paragraph("Results: None available", styles['BodyText']))
				elements.append(Paragraph("Discussion: None available", styles['BodyText']))
				elements.append(Paragraph("Conclusion: None available", styles['BodyText']))
				elements.append(Spacer(1, 12))

		elements.append(PageBreak())

	doc.build(elements)
	pdf_buffer.seek(0)
	return pdf_buffer

def parse_html_table(html):
	soup = BeautifulSoup(html, 'html.parser')
	table = []
	for row in soup.find_all('tr'):
		cells = [cell.get_text(strip=True) for cell in row.find_all(['th', 'td'])]
		table.append(cells)
	return table

def parse_ovid_xml(file):
	tree = ET.parse(file)
	root = tree.getroot()
	articles = []
	for record in root.findall(".//record"):
		title = record.find(".//F[@C='ti']/D").text if record.find(".//F[@C='ti']/D") is not None else ""
		authors = "; ".join([author.text for author in record.findall(".//F[@C='au']/D")])
		abstract = record.find(".//F[@C='ab']/D").text if record.find(".//F[@C='ab']/D") is not None else ""
		journal = record.find(".//F[@C='jn']/D").text if record.find(".//F[@C='jn']/D") is not None else ""
		pub_date = record.find(".//F[@C='dp']/D").text if record.find(".//F[@C='dp']/D") is not None else ""
		issn = record.find(".//F[@C='is']/D").text if record.find(".//F[@C='is']/D") is not None else ""
		link = record.find(".//F[@C='link']/T").text if record.find(".//F[@C='link']/T") is not None else ""
		doi = record.find(".//F[@C='do']/D").text[18:] if record.find(".//F[@C='do']/D") is not None else ""
		pmid = record.find(".//F[@C='pmid']/D").text if record.find(".//F[@C='pmid']/D") is not None else ""

		# Limit cell content to 6000 characters
		title = title[:6000]
		abstract = abstract[:6000]
		authors = authors[:6000]

		article_data = {
			"title": title,
			"abstract": abstract,
			"authors": authors,
			"journal": journal,
			"pub_date": pub_date,
			"issn": issn,
			"doi": doi,
			"link": link,
			"pmid": pmid,
			"label": ""  # Placeholder for label
		}
		articles.append(article_data)

	return articles

@app.route('/')
def index():
	return render_template('search_AI.html')

@app.route('/search', methods=['GET', 'POST'])
def search():
	if request.method == 'POST':
		query = request.form['query']

		id_list, count = search_pubmed(query)
		if not id_list:
			return "No records found."

		pubmed_records = fetch_pubmed_details(id_list)
		articles = parse_pubmed_xml(pubmed_records)
		count = len(articles)

		filename_query = re.sub(r'\W+', '_', query)[:150]
		filename = f"pubmed_data_{filename_query}.csv"
		csv_buffer = BytesIO()
		pd.DataFrame(articles).to_csv(csv_buffer, index=False)
		csv_buffer.seek(0)

		# Store the PubMed results in a file
		pubmed_file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
		with open(pubmed_file_path, 'wb') as f:
			f.write(csv_buffer.getvalue())

		# Store the file path in the session
		session['pubmed_file_path'] = pubmed_file_path

		# Generate a unique URL for the file download
		file_url = url_for('download_csv', filename=filename)

		return render_template('results_AI.html', query=query, articles=articles, count=count, file_url=file_url)
	else:
		query = request.args.get('query')
		if not query:
			return "Query parameter is missing."

		articles, count, file_path = handle_search_and_load(query)
		if articles is None:
			return "File not found."

		return render_template('results_AI.html', query=query, articles=articles, count=count)

@app.route('/download_csv/<filename>')
def download_csv(filename):
	file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
	return send_file(file_path, mimetype='text/csv', as_attachment=True, download_name=filename)

@app.route('/upload_ovid_xml', methods=['POST'])
def upload_ovid_xml():
	if 'ovid_files' not in request.files:
		return jsonify({"error": "No file part"}), 400
	files = request.files.getlist('ovid_files')
	if not files:
		return jsonify({"error": "No selected file"}), 400

	ovid_articles = []
	for file in files:
		if file and allowed_file(file.filename):
			ovid_articles.extend(parse_ovid_xml(file))

	# Get the PubMed results from the file
	if 'pubmed_file_path' not in session:
		return "No PubMed results to combine with."

	pubmed_file_path = session['pubmed_file_path']
	df_pubmed = pd.read_csv(pubmed_file_path)
	pubmed_articles = df_pubmed.to_dict(orient='records')

	combined_articles = pubmed_articles + ovid_articles

	# Save the combined data in a file
	combined_df = pd.DataFrame(combined_articles)
	combined_file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'combined_data.csv')
	combined_df.to_csv(combined_file_path, index=False)

	# Store the combined file path in the session
	session['combined_file_path'] = combined_file_path

	# Automatically download the combined results
	return send_file(combined_file_path, mimetype='text/csv', as_attachment=True, download_name='combined_data.csv')

@app.route('/upload_asreview_csv', methods=['POST'])
def upload_asreview_csv():
	if 'file' not in request.files:
		return "No file part"
	file = request.files['file']
	if file.filename == '':
		return "No selected file"
	if file:
		filename = secure_filename(file.filename)
		asreview_file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
		file.save(asreview_file_path)
		session['asreview_file_path'] = asreview_file_path
		return redirect(url_for('show_uploaded_csv'))

@app.route('/show_uploaded_csv')
def show_uploaded_csv():
	if 'asreview_file_path' not in session:
		return "No ASReview results uploaded."
	asreview_file_path = session['asreview_file_path']
	df = pd.read_csv(asreview_file_path)
	articles = df.to_dict(orient='records')
	count = len(articles)
	return render_template('uploaded_results_AI.html', articles=articles, count=count)

@app.route('/generate_pdf_route', methods=['POST'])
def generate_pdf_route():
	try:
		num_articles = int(request.form['num_articles'])
		query = request.form.get('query', 'query').replace(' ', '_')

		# Get ASReview results from file
		if 'asreview_file_path' not in session:
			return "No ASReview results to generate PDF."

		asreview_file_path = session['asreview_file_path']
		df_asreview = pd.read_csv(asreview_file_path)
		asreview_articles = df_asreview.to_dict(orient='records')

		pdf_buffer = create_pdf_buffer(asreview_articles, num_articles, query)

		return send_file(pdf_buffer, mimetype='application/pdf', as_attachment=True, download_name='articles.pdf')
	except Exception as e:
		return str(e)

@app.route('/start_asreview', methods=['POST'])
def start_asreview():
	try:
		subprocess.Popen(["asreview", "lab", "--port", "5001"])
		return redirect("http://localhost:5001/")
	except Exception as e:
		return str(e)

def allowed_file(filename):
	return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'xml'}

if __name__ == '__main__':
	app.run(host='0.0.0.0', port=5002, debug=True)

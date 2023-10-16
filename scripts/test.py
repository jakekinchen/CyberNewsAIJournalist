from bs4 import BeautifulSoup
import re

class HTMLMetrics:

    # Common transition words (this list can be expanded)
    TRANSITION_WORDS = ["however", "therefore", "moreover", "furthermore", "thus", "also", "then", 
                        "firstly", "secondly", "next", "finally", "in addition", "meanwhile", "for example"]

    def __init__(self, html):
        self.soup = BeautifulSoup(html, 'html.parser')
        self.text = self.soup.get_text()
        self.sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', self.text)

    def subheading_distribution(self):
        # Get sections between headings or between heading and end of document
        sections = self.soup.find_all(re.compile('^h[1-6]$'))
        long_sections = 0

        for i in range(len(sections) - 1):
            section_text = self.soup.get_text(sections[i].next_sibling, sections[i+1])
            word_count = len(section_text.split())
            if word_count > 300:
                long_sections += 1

        # Check last section till end of document
        if sections:
            last_section_text = self.soup.get_text(sections[-1].next_sibling)
            if len(last_section_text.split()) > 300:
                long_sections += 1

        return long_sections

    def sentence_length(self):
        long_sentences = sum(1 for sentence in self.sentences if len(sentence.split()) > 20)
        return (long_sentences / len(self.sentences)) * 100

    def transition_words(self):
        transition_sentences = sum(1 for sentence in self.sentences if any(word in sentence.lower() for word in self.TRANSITION_WORDS))
        return (transition_sentences / len(self.sentences)) * 100

# Test with sample HTML
sample_html = """
<h1>Title</h1>
<p>This is a sentence. However, this is another sentence. This is a very long sentence that contains more than twenty words and should be flagged. Next, we move on.</p>
<h2>Subheading</h2>
<p>This section is okay. It doesn't have too many words and should not be flagged. For example, this is a short sentence. Furthermore, this is another one.</p>
<h2>Another Subheading</h2>
<p>This is another section. It is also fine. Meanwhile, let's continue with the next section.</p>
"""

metrics = HTMLMetrics(sample_html)
subheading_issues = metrics.subheading_distribution()
sentence_length_percentage = metrics.sentence_length()
transition_word_percentage = metrics.transition_words()

subheading_issues, sentence_length_percentage, transition_word_percentage

from bs4 import BeautifulSoup, Tag
import math
import re
import os
from gpt_utils import query_gpt

class ReadabilityMetrics:
    class TrieNode:
        def __init__(self):
            self.children = {}
            self.is_end_of_word = False

    class Trie:
        def __init__(self):
            self.root = ReadabilityMetrics.TrieNode()

        def insert(self, word):
            node = self.root
            for char in word:
                if char not in node.children:
                    node.children[char] = ReadabilityMetrics.TrieNode()
                node = node.children[char]
            node.is_end_of_word = True

        def search(self, word):
            node = self.root
            for char in word:
                if char not in node.children:
                    return False
                node = node.children[char]
            return node.is_end_of_word

        def search_in_sentence(self, sentence):
            words = sentence.split()
            for i in range(len(words)):
                temp_word = words[i]
                if self.search(temp_word):
                    return True
                for j in range(i+1, len(words)):
                    temp_word += " " + words[j]
                    if self.search(temp_word):
                        return True
            return False

    # Common transition words (this list can be expanded)
    TRANSITION_WORDS = ["accordingly", "additionally", "afterward", "afterwards", "albeit", "also", "although", "altogether", "another", "basically", "because", "before", "besides", "but", "certainly", "chiefly", "comparatively", "concurrently", "consequently", "contrarily", "conversely", "correspondingly", "despite", "doubtedly", "during", "e.g.", "earlier", "emphatically", "equally", "especially", "eventually", "evidently", "explicitly", "finally", "firstly", "following", "formerly", "forthwith", "fourthly", "further", "furthermore", "generally", "hence", "henceforth", "however", "i.e.", "identically", "indeed", "instead", "last", "lastly", "later", "lest", "likewise", "markedly", "meanwhile", "moreover", "nevertheless", "nonetheless", "nor", "notwithstanding", "obviously", "occasionally", "otherwise", "once", "overall", "particularly", "presently", "previously", "rather", "regardless", "secondly", "shortly", "significantly", "similarly", "simultaneously", "since", "so", "soon", "specifically", "still", "straightaway", "subsequently", "surely", "surprisingly", "than", "then", "thereafter", "therefore", "thereupon", "thirdly", "though", "thus", "till", "undeniably", "undoubtedly", "unless", "unlike", "unquestionably", "until", "when", "whenever", "whereas", "while", "above all", "after all", "after that", "all in all", "all of a sudden", "all things considered", "analogous to", "although this may be true", "another key point", "as a matter of fact", "as a result", "as an illustration", "as can be seen", "as has been noted", "as I have noted", "as I have said", "as I have shown", "as long as", "as much as", "as shown above", "as soon as", "as well as", "at any rate", "at first", "at last", "at least", "at length", "at the present time", "at the same time", "at this instant", "at this point", "at this time", "balanced against", "being that", "by all means", "by and large", "by comparison", "by the same token", "by the time", "compared to", "be that as it may", "coupled with", "different from", "due to", "equally important", "even if", "even more", "even so", "even though", "first thing to remember", "for example", "for fear that", "for instance", "for one thing", "for that reason", "for the most part", "for the purpose of", "for the same reason", "for this purpose", "for this reason", "from time to time", "given that", "given these points", "important to realize", "once in a while", "in a word", "in addition", "in another case", "in any case", "in any event", "in brief", "in case", "in conclusion", "in contrast", "in detail", "in due time", "in effect", "in either case", "in essence", "in fact", "in general", "in light of", "in like fashion", "in like manner", "in order that", "in order to", "in other words", "in particular", "in reality", "in short", "in similar fashion", "in spite of", "in sum", "in summary", "in that case", "in the event that", "in the final analysis", "in the first place", "in the fourth place", "in the hope that", "in the light of", "in the long run", "in the meantime", "in the same fashion", "in the same way", "in the second place", "in the third place", "in this case", "in this situation", "in time", "in truth", "in view of", "most compelling evidence", "most important", "must be remembered", "not to mention", "now that", "of course", "on account of", "on balance", "on condition that", "on one hand", "on the condition that", "on the contrary", "on the negative side", "on the other hand", "on the positive side", "on the whole", "on this occasion", "only if", "owing to", "point often overlooked", "prior to", "provided that", "seeing that", "so as to", "so far", "so long as", "so that", "sooner or later", "such as", "summing up", "take the case of", "that is", "that is to say", "then again", "this time", "to be sure", "to begin with", "to clarify", "to conclude", "to demonstrate", "to emphasize", "to enumerate", "to explain", "to illustrate", "to list", "to point out", "to put it another way", "to put it differently", "to repeat", "to rephrase it", "to say nothing of", "to sum up", "to summarize", "to that end", "to the end that", "to this end", "together with", "under those circumstances", "until now", "up against", "up to the present time", "vis a vis", "whatÕs more", "while it may be true", "while this may be true", "with attention to", "with the result that", "with this in mind", "with this intention", "with this purpose in mind", "with attention to", "with the result that", "with this in mind", "with this intention", "with this purpose in mind", "without a doubt", "without delay", "without doubt", "without reservation", "both ... and", "if ... then", "not only ... but also", "neither ... nor", "whether ... or", "no sooner ... than"]

    def __init__(self, html):
        self.soup = BeautifulSoup(html, 'html.parser')
        self.text = self.soup.get_text()
        self.sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', self.text)
        self.trie = self.Trie()
        for word in self.TRANSITION_WORDS:
            self.trie.insert(word)
        self.paragraphs = self.soup.find_all('p')

    def sanitize_text(self, text):
        # Remove unwanted characters from text, convert to lowercase, and remove spaces.
        return re.sub(r'[^\w\s]', '', text).lower().replace(" ", "")

    def readability_score(self):
        """
        Calculate the readability score based on various criteria.
        For demonstration, we're just using a simple average.
        """
        # These weights can be adjusted based on importance
        weights = {
            'paragraph_length': 1,
            'transition_words': 1,
            'passive_voice': 1,
            'sentence_length': 1
        }
        
        score = 0
        score += weights['paragraph_length'] * sum(self.score_paragraph_length())
        score += weights['transition_words'] * self.transition_words()
        score += weights['passive_voice'] * self.passive_voice_percentage()
        score += weights['sentence_length'] * self.sentence_length()
        
        return score / sum(weights.values())
    
    def optimize(self):
        max_iterations = 5
        iteration = 0

        # Step 1: Optimize paragraphs based on length and transitions.
        while iteration < max_iterations:
            ranked_paragraphs = self.rank_paragraphs()
            if not ranked_paragraphs:  # Check if the ranked list is empty
                break
            # If the top-ranked paragraph's score is below a certain threshold, break.
            paragraph_text = self.paragraphs[ranked_paragraphs[0]].text
            if self.score_paragraph(paragraph_text) < 200:
                break
            self.optimize_paragraph(ranked_paragraphs[0])
            iteration += 1

        # Step 2: Once paragraphs are optimized, optimize individual sentences if needed.
        long_sentences = [s for s in self.sentences if len(s.split()) > 20]
        passive_sentences = self.passive_voice_sentences()

        # Combine the sentences and remove duplicates
        sentences_to_optimize = list(set(long_sentences + passive_sentences))
        for sentence in sentences_to_optimize:
            optimized_sentence = self.optimize_sentence(sentence)
            self.text = self.text.replace(sentence, optimized_sentence)

        # Update the text content after optimization using the entire parsed HTML
        self.text = str(self.soup)

    def optimize_readability(self):
        """
        Optimize the content for readability.
        Return the improved content or the original.
        """
        initial_score = self.readability_score()
        print(f"Initial Readability Score: {initial_score}")
        #print(f"self.text: {self.text}")
        self.optimize()

        final_score = self.readability_score()
        print(f"Final Readability Score: {final_score}")

        # If the final score is worse than the initial score or if there's no improvement, return the original content
        if final_score <= initial_score:
            return self.text

        # Otherwise, return the optimized content
        return self.text

    def rank_paragraphs(self):
        if not self.paragraphs:
            return []
        # Rank paragraphs based on multiple criteria.
        scores = [(i, self.score_paragraph(p.text)) for i, p in enumerate(self.paragraphs)]
        scores.sort(key=lambda x: x[1], reverse=True)
        return [s[0] for s in scores]

    def score_paragraph(self, paragraph):
        # Aggregate score for a given paragraph based on different criteria.
        score = 0
        # Prioritize paragraphs over 300 words by setting a high penalty.
        if len(paragraph.split()) > 300:
            score += 1000
        score += (1 - self.transition_words(paragraph)) * 100  # Adjusted this line
        score += (1 - self.passive_voice_percentage(paragraph)) * 100  # Assuming you have or will have this method
        return score

    def optimize_paragraph(self, index):
        #print(f"Number of paragraphs: {len(self.paragraphs)}")
        # Use GPT to optimize the given paragraph and return the optimized version.
        paragraph = self.paragraphs[index].text
        system_prompt = "You are a brilliant editor for the New York Times"
        user_prompt = (f"Please optimize the following paragraph from a blog post. "
                f"Break it into shorter paragraphs if it's too long, "
                f"maintain an active voice, don't use sentences longer than 20 words, and use appropriate transition words. "
                f"Don't include anything extra besides the paragraphs.\n\n"
                f"Paragraph:\n{paragraph}")
        optimized_text = query_gpt(user_prompt, system_prompt, model=os.getenv('FUNCTION_CALL_MODEL'))
        
        # Here we replace the text of the existing paragraph Tag with the optimized text
        new_paragraph = self.soup.new_tag('p')
        new_paragraph.string = optimized_text
        self.paragraphs[index] = new_paragraph
    
    def optimize_sentence(self, sentence):
        # Use GPT to optimize the given sentence and return the optimized version.
        system_prompt = "You are a brilliant editor for the New York Times"
        user_prompt = (f"Please optimize the following sentence from a blog post. "
                  f"Maintain an active voice, and don't use sentences longer than 20 words. "
                  f"Don't include anything extra besides the sentence.\n\n"
                  f"Sentence:\n{sentence}")
        return query_gpt(user_prompt, system_prompt, model=os.getenv('FUNCTION_CALL_MODEL'))
        
    def score_paragraph_length(self):
        # Score paragraphs based on length. Return a list of scores for each paragraph.
        return [len(paragraph.text.split()) for paragraph in self.paragraphs]

    def contains_two_part_transition(self, sentence, two_part_words):
        for part1, part2 in two_part_words:
            if part1 in sentence and part2 in sentence:
                return True
        return False

    def transition_words(self, paragraph=None):
        # Extract two-part transition words
        two_part_words = [tuple(word.split('...')) for word in self.TRANSITION_WORDS if '...' in word]
        
        sentences = self.sentences
        if paragraph:  # If a specific paragraph is provided
            sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', paragraph)
        
        transition_sentences = sum(1 for sentence in sentences if self.trie.search_in_sentence(sentence.lower()) or 
                                self.contains_two_part_transition(sentence.lower(), two_part_words))

        return (transition_sentences / len(sentences)) * 100

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
    
    def locate_paragraphs_longer_than_300_words(self):
        # Return the numbers of paragraphs that are longer than 300 words
        paragraphs = self.soup.find_all('p')
        long_paragraphs = [i + 1 for i, paragraph in enumerate(paragraphs) if len(paragraph.text.split()) > 300]
        return long_paragraphs
    
    def is_passive_sentence(self, sentence):
        # A basic check for passive voice (can be enhanced)
        be_verbs = ["is", "was", "were", "are", "be", "being", "been"]
        tokens = sentence.split()
        for i, token in enumerate(tokens[:-1]):
            if token in be_verbs and tokens[i+1][-2:] == "ed":  # checking for past participle
                return True
        return False

    def passive_voice_sentences(self, paragraph=None):
        sentences = self.sentences
        if paragraph:  # If a specific paragraph is provided
            sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', paragraph)
        return [sentence for sentence in sentences if self.is_passive_sentence(sentence)]

    def passive_voice_percentage(self, paragraph=None):
        passive_sentences = self.passive_voice_sentences(paragraph)
        sentences = self.sentences
        if paragraph:  # If a specific paragraph is provided
            sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', paragraph)
        return (len(passive_sentences) / len(sentences)) * 100

    def transform_passive_to_active(self):
        passive_sentences = self.passive_voice_sentences()
        for sentence in passive_sentences:
            # Here, you'll call GPT to transform the sentence to active voice
            system_prompt = "The following is a sentence from a blog post. Please transform the passive voice sentences to active voice while maintaing any syntax. Don't include anything extra besides the active voice sentence."
            user_prompt = f"Here is the sentence: {sentence}"
            active_sentence = query_gpt(system_prompt, user_prompt, 'gpt-3.5-turbo')
            # Replace the passive sentence in the text with the active one
            if active_sentence:
                self.text = self.text.replace(sentence, active_sentence)
                if self.passive_voice_percentage() < 10:
                    break
    
class SeoMetrics:
    def __init__(self, post_info, images):
        self.post_info = post_info
        self.content = post_info['content']
        self.soup = BeautifulSoup(self.content, 'html.parser')
        self.keyword = self.post_info['yoast_meta']['yoast_wpseo_focuskw']
        self.meta_description = self.post_info['yoast_meta']['yoast_wpseo_metadesc']
        self.seo_title = self.post_info['yoast_meta']['yoast_wpseo_title']
        self.images = images

        # If keyword is not provided, regenerate a focus keyword.
        if not self.keyword:
            self.keyword = self.regenerate_focus_keyword()
        
        # Store a sanitized version of the keyword.
        self.sanitized_keyword = self.sanitize_text(self.keyword)

    def assess_needs(self):
        needs = {
            "keyword_in_intro": self.keyword_in_intro(),
            "keyword_in_seo_title": self.keyword_in_seo_title(),
            "keyword_in_image_alt": self.keyword_in_image_alt(),
            "meta_description_length": self.meta_description_length(),
        }
        return needs

    def optimize(self):
        # Get the score before optimization
        score_before = self.compute_score()

         # Perform optimization
        seo_needs = self.assess_needs()

        if not seo_needs["keyword_in_intro"]:
            self.rewrite_intro()
        if not seo_needs["keyword_in_seo_title"]:
            self.rewrite_seo_title()
        
        if not seo_needs["meta_description_length"]:
            self.rewrite_meta_description()
        
        # Update the post_info dictionary with the optimized values
        self.post_info['content'] = self.content
        self.post_info['content'] = self.format_post()
        self.post_info['yoast_meta']['yoast_wpseo_focuskw'] = self.keyword
        self.post_info['yoast_meta']['yoast_wpseo_metadesc'] = self.meta_description
        self.post_info['yoast_meta']['yoast_wpseo_title'] = self.seo_title

        self.post_info = self.inject_images_into_post_info()
        if not seo_needs["keyword_in_image_alt"]:
            self.add_keyword_to_image_alt()

         # Get the score after optimization
        score_after = self.compute_score()

        # Print or log the scores for comparison
        print(f"SEO Score before optimization: {score_before}")
        print(f"SEO Score after optimization: {score_after}")

        return self.post_info
    
    def compute_score(self):
        # Here, each criterion is given an equal weight of 25 points.
        # If all criteria are satisfied, the total score is 100.
        # You can adjust the weights based on the importance of each criterion.
        score = 0
        seo_needs = self.assess_needs()
        if seo_needs["keyword_in_intro"]:
            score += 25
        if seo_needs["keyword_in_seo_title"]:
            score += 25
        if seo_needs["keyword_in_image_alt"]:
            score += 25
        if seo_needs["meta_description_length"]:
            score += 25
        return score

    def regenerate_focus_keyword(self):
        system_prompt = ("Generate a focus keyword for the article title. The focus keyword should be "
                         "a word or phrase that is the most relevant to the article. It should be a word "
                         "or phrase that is most likely to be searched for by someone who is looking for "
                         "information about the topic of the article. It should be 1-3 words but NOT cybersecurity by itself.")
        user_prompt = f"Focus keyword for {self.post_info['title']}:"
        return query_gpt(user_prompt, system_prompt, model='gpt-3.5-turbo')

    def sanitize_text(self, text):
    # Remove unwanted characters from text, convert to lowercase, and remove spaces.
        return re.sub(r'[^\w\s]', '', text).lower().replace(" ", "")
    
    def add_keyword_to_image_alt(self):
        # Isolate all image tags and their alt attributes, and concatenate the keywords to the alt attributes
        image_tags = self.soup.find_all('img')
        for image_tag in image_tags:
            alt = image_tag.get('alt', '')
            image_tag['alt'] = f"{alt}, {self.keyword}"
        self.content = str(self.soup)

    def keyword_in_intro(self):
        # Check if the keyword is in the first paragraph
        first_paragraph = self.soup.find('p')
        if first_paragraph:
            sanitized_text = self.sanitize_text(first_paragraph.text)
            return self.sanitized_keyword in sanitized_text
        return False

    def keyword_in_seo_title(self):
        # Check if keyword appears in the SEO title
        seo_title = self.sanitize_text(self.seo_title)
        return self.sanitized_keyword in seo_title

    def keyword_in_image_alt(self):
        # Locate the alt attribute of all images and check if they contain the keyword
        images = self.soup.find_all('img')
        for image in images:
            if image.has_attr('alt'):
                alt_text = self.sanitize_text(image['alt'])
                if self.sanitized_keyword in alt_text:
                    return True
        return False
    
    def meta_description_length(self):
        # Check the length of the meta description
        return len(self.meta_description) >= 120 and len(self.meta_description) <= 156
    
    def rewrite_seo_title(self):
        prompt = f"Rewrite the SEO title to include the keyphrase \"{self.keyword}\". The current SEO title is: {self.seo_title}"
        response_machine_prompt = "Follow the instructions to rewrite a short SEO title."
        rewritten_seo_title = query_gpt(prompt, response_machine_prompt, model='gpt-3.5-turbo')
        if rewritten_seo_title:
            self.seo_title = rewritten_seo_title  # Save the updated value
        else:
            print("Failed to rewrite the SEO title. Continuing...")
        
    def correct_meta_description_length(self):
        return len(self.meta_description) >= 120 and len(self.meta_description) <= 156

    def rewrite_meta_description(self):
        # Define the length adjustment
        if len(self.meta_description) <= 120:
            length = 'slightly longer'
        else:  # len(meta_description) >= 156:
            length = 'slightly shorter'
        
        # Formulate the GPT prompt
        prompt = f"Rewrite the meta description to include the keyphrase \"{self.keyword}\" and to be {length}. The current meta description is: {self.meta_description}"
        response_machine_prompt = "Follow the instructions to rewrite the meta description."

        # Query GPT
        rewritten_meta_description = query_gpt(prompt, response_machine_prompt, model='gpt-3.5-turbo')
        
        # Define a helper function to check if the meta description fits the requirements
        def is_meta_valid(meta):
            sanitized_meta = self.sanitize_text(meta)
            return 120 < len(meta) <= 156 and self.sanitized_keyword in sanitized_meta

        # Check the validity of the meta description
        while not is_meta_valid(rewritten_meta_description):
            if len(rewritten_meta_description) > 156:
                # Remove the last sentence
                last_sentence_end = max(rewritten_meta_description.rfind('.'), rewritten_meta_description.rfind('!'))
                rewritten_meta_description = rewritten_meta_description[:last_sentence_end]
            else:
                # Try to adjust the meta description again
                rewritten_meta_description = query_gpt(prompt, response_machine_prompt, model='gpt-3.5-turbo')

         # If the description is valid, update it, otherwise keep the original
        if is_meta_valid(rewritten_meta_description):
            self.meta_description = rewritten_meta_description  # Save the updated value
        else:
            print("Failed to rewrite the meta description. Returning the original.")

    def rewrite_intro(self):
        soup = BeautifulSoup(self.content, 'html.parser')
        
        # Isolate the first paragraph tag
        first_paragraph_tag = soup.find('p')
        
        if not first_paragraph_tag:
            print("No paragraph found")
            return self.content  # Return original content if no paragraph is found
        
        # Extract the complete first paragraph including the <p> tags
        first_paragraph = str(first_paragraph_tag)
        
        # Formulate a GPT prompt to rewrite the first paragraph with the keyword
        prompt = f"Rewrite the first paragraph to include the keyphrase \"{self.keyword}\". The first paragraph is: {first_paragraph}"
        response_machine_prompt = "Follow the instructions to rewrite the first paragraph. maintain an active voice, keep any previous HTML syntax, don't use sentences longer than 20 words, don't make the introduction too long, and use appropriate transition words."
        
        # Query GPT to rewrite the first paragraph
        rewritten_first_paragraph = query_gpt(prompt, response_machine_prompt, model='gpt-3.5-turbo')
        
        # Ensure the rewritten paragraph is surrounded by <p> tags
        if not rewritten_first_paragraph.startswith('<p>'):
            rewritten_first_paragraph = '<p>' + rewritten_first_paragraph
        if not rewritten_first_paragraph.endswith('</p>'):
            rewritten_first_paragraph += '</p>'
        
        # Replace the first paragraph with the rewritten paragraph
        self.content = self.content.replace(first_paragraph, rewritten_first_paragraph, 1)  # Only replace the first occurrence
        
        return self.content
    
    def format_post(self):
        # Clean the input content
        cleaned_content = self._clean_input_content(self.post_info['content'])
        
        # Beginning with the doctype, header, and meta information
        html_content = """
<body>
<div style="max-width:640px; margin: auto;">
<header>
    <h1 style="font-size: larger;">{title}</h1>
</header>
<section>
""".format(title=self.post_info['title'])

        # If there's an image associated with the post, add it after the title
        if 'image_url' in self.post_info and self.post_info['image_url']:
            html_content += '<img src="{}" alt="Image for {}" style="width:100%; height:auto;">\n'.format(self.post_info['image_url'], self.post_info['title'])


        # Add the cleaned content wrapped inside <article>
        html_content += "<article>\n" + cleaned_content + "</article>\n</section>\n"

        # Close the body and html tags
        html_content += "</body>"

        # Beautify the output using BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        return soup.prettify()

    def _clean_input_content(self, content):
        """
        Helper method to clean input content:
        - Remove any existing HTML structure
        - Extract only the textual content and desired attributes (like hyperlinks)
        """
        soup = BeautifulSoup(content, 'html.parser')

        # Remove any non-text elements (like script or style tags)
        for script in soup(['script', 'style']):
            script.extract()

        # Extract text and wrap in paragraphs
        paragraphs = soup.get_text().split('\n')
        cleaned_content = ""
        for paragraph in paragraphs:
            # Ensure paragraph isn't just whitespace or a duplicate of the title
            if paragraph.strip() and paragraph != self.post_info['title']:
                cleaned_content += '    <p style="margin-top: 1em; font-size: 1.1em;">{}</p>\n'.format(paragraph)
        
        return cleaned_content
    
    def inject_images_into_post_info(self):
        #print(f"Parameters: post_info: {post_info}, images: {images}, keyword: {keyword}")
        keyword = self.post_info['yoast_meta']['yoast_wpseo_focuskw']
        
        if not self.images:  # If images are empty or None
            raise Exception("No images to inject into post info.")
        
        # Initialize BeautifulSoup object with the post content
        soup = BeautifulSoup(self.post_info['content'], 'html.parser')
        
        sanitized_keyword = None
        if keyword:
            sanitized_keyword = self.sanitize_text(keyword)
        else:
            print("No focus keyword found in post_info.")
        
        # Get all the paragraphs in the body
        p_tags = soup.find_all('p')
        
        # If there is only one image, insert it under the h1 tag
        if len(self.images) == 1:
            img_tag = soup.new_tag("img", src=self.images[0]['wp_url'], alt=self.images[0]['description'])
            h1_tag = soup.find('h1')
            if h1_tag:
                h1_tag.insert_after(img_tag)
            else:
                print("No h1 tag found.")
            
            self.post_info['featured_media'] = self.images[0]['wp_id']

            # Ensure the alt text is not None
            if img_tag['alt'] is None:
                img_tag['alt'] = ""

            sanitized_img_alt = self.sanitize_text(img_tag['alt'])
            
            if sanitized_keyword and sanitized_keyword not in sanitized_img_alt:
                img_tag['alt'] += f", {keyword}"
            else:
                print("Keyword already present in image alt or no keyword to add.")
        else:
            print(f"{len(self.images)} images found. Distributing across content...")
            self.post_info = self.distribute_images(p_tags)
        
        self.post_info['content'] = str(soup)
        print("Finished injecting images.")
        return self.post_info
    
    def distribute_images(self, p_tags):
        # Calculate the interval at which to insert the images
        interval = len(p_tags) / (len(self.images) + 1)
        for i, image in enumerate(self.images):
            # Calculate the index at which to insert the current image
            index = math.ceil(interval * (i + 1))
            # If it exceeds the last index, set it to the last index
            if index >= len(p_tags):
                index = len(p_tags) - 1
            # Create and insert the image tag
            img_tag = Tag(name='img', attrs={'src': image['wp_url'], 'alt': image['description']})
            img_tag['width'] = '640'
            img_tag['height'] = '360'
            p_tags[index].insert_before(img_tag)
            
            # Set the featured_media for the first image
            if i == 0:
                self.post_info['featured_media'] = image['wp_id']
                
            # Add focus keyword to alt attribute if not present
            if self.post_info['yoast_wpseo_focuskw'] and self.post_info['yoast_wpseo_focuskw'] not in img_tag['alt']:
                img_tag['alt'] += f", {self.post_info['yoast_wpseo_focuskw']}"

    def test_inject_images_into_post_info(self):
        post_info = {
            'content': '<html><head> <title>The Emergent Cyber Threat of North Korean Actors: From TeamCity Exploits to Operation Dream Magic</title></head><body><h1>The Emergent Cyber Threat of North Korean Actors: From TeamCity Exploits to Operation Dream Magic</h1><img alt="Korean Food Bibimbap with Kimchi, North Korean Cyber Threat" src="https://cybernow.info/wp-content/uploads/2023/10/4f4YZfDMLeU.jpeg"/><p><strong>North Korean Cyber Threat:</strong> The cybersecurity threat posed by North Korean threat actors persists. An example of this is the recent warning issued by Microsoft about these actors, specifically focusing on the Lazarus Group<sup><a href="https://www.microsoft.com/en-us/security/blog/2023/10/18/multiple-north-korean-threat-actors-exploiting-the-teamcity-cve-2023-42793-vulnerability/"> 1</a></sup>.</p><p>They are found exploiting a critical flaw in JetBrains TeamCity. This vulnerability referenced is coined CVE-2023-42793<sup><a href="https://symantec-enterprise-blogs.security.com/blogs/threat-intelligence/lazarus-dream-job-chemical"> 2</a></sup>. This significant flaw comes with a notable CVSS score of 9.8, signifying its seriousness.</p><p>The North Korean actors of interest, Diamond Sleet and Onyx Sleet, use sophisticated tools in their cyber-attacks. Such development indicates their enhanced capabilities<sup><a href="https://malpedia.caad.fkie.fraunhofer.de/details/win.tinynuke"> 3</a></sup>.</p><p>Lazarus Group reveals its stealth and persistence through its use of malware like Volgmer and Scout<sup><a href="https://asec.ahnlab.com/en/57736/"> 4</a></sup>.</p></body></html>If you enjoyed this article, please check out our other articles on <a href="https://cybernow.info">CyberNow</a>',
            'yoast_meta':
                {
                'yoast_wpseo_focuskw': 'KEYWORD',
                }
            
        }
        images = [
                {
                    'wp_url': 'https://www.google.com/images/branding/googlelogo/2x/googlelogo_color_92x30dp.png',
                    'description': 'Google logo',
                    'wp_id': '1234'
                }
            ]

        try:
            result = self.inject_images_into_post_info(self.post_info, self.images)
            
            # Example assertions (you might need more depending on what you expect)
            assert 'Google logo' in result['content']
            # ... add more assertions as needed
            
        except Exception as e:
            assert False, f"Test failed with exception: {e}"

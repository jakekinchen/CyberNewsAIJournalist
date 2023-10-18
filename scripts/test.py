from bs4 import BeautifulSoup
import re

class HTMLMetrics:
    class TrieNode:
        def __init__(self):
            self.children = {}
            self.is_end_of_word = False

    class Trie:
        def __init__(self):
            self.root = HTMLMetrics.TrieNode()

        def insert(self, word):
            node = self.root
            for char in word:
                if char not in node.children:
                    node.children[char] = HTMLMetrics.TrieNode()
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
        self.trie = self.Trie()  # Initialize a new Trie for this instance
        for word in self.TRANSITION_WORDS:
            self.trie.insert(word)

    def contains_two_part_transition(self, sentence, two_part_words):
        for part1, part2 in two_part_words:
            if part1 in sentence and part2 in sentence:
                return True
        return False

    def transition_words(self):
        # Extract two-part transition words
        two_part_words = [tuple(word.split('...')) for word in self.TRANSITION_WORDS if '...' in word]

        transition_sentences = sum(1 for sentence in self.sentences if self.trie.search_in_sentence(sentence.lower()) or 
                                  self.contains_two_part_transition(sentence.lower(), two_part_words))

        return (transition_sentences / len(self.sentences)) * 100

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

    
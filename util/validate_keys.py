import re
import logging
from typing import List, Dict, Optional, Tuple, Set

logger = logging.getLogger(__name__)

class KeyValidator:
    def __init__(self, texto_original: str, expected_keys: Optional[List[str]] = None):
        self.texto_original = texto_original
        # Default expected keys if none provided
        self.expected_keys = expected_keys or [
            'MUNICÍPIO', 'ÓRGÃO', 'EXERCÍCIO', 'ASSUNTO', 'ORDENADORES', 
            'CONTADORA', 'MPC', 'RELATOR', 'EMENTA', 'DECISÃO'
        ]
        # Common noise words that might appear before a colon but aren't keys
        self.noise_words = {
            'CPF', 'CNPJ', 'ENDEREÇO', 'CEP', 'TELEFONE', 'EMAIL', 'E-MAIL', 'HORA'
        }
        
    def get_validated_keys(self) -> List[str]:
        """
        Returns a validated list of keys from the text.
        """
        # First pass - get potential key candidates
        potential_keys = self._get_potential_keys()
        
        # Second pass - validate keys against expected and context
        validated_keys = self._validate_keys(potential_keys)
        
        logger.info(f"Validated keys: {validated_keys}")
        return validated_keys
    
    def _get_potential_keys(self) -> List[Tuple[str, int]]:
        """
        First pass to extract potential keys with their positions in the text.
        Returns a list of tuples (key, position)
        """
        # This pattern looks for uppercase words followed by a colon
        # Improved to handle more cases
        pattern = r'(?<!\w)((?:[A-ZÁÉÍÓÚÀÂÊÔÇÜÃÕÑ][A-ZÁÉÍÓÚÀÂÊÔÇÜÃÕÑ\s\-\_]*[A-ZÁÉÍÓÚÀÂÊÔÇÜÃÕÑ])|(?:[A-ZÁÉÍÓÚÀÂÊÔÇÜÃÕÑ]))(?=\s*:)'
        
        matches = []
        for match in re.finditer(pattern, self.texto_original):
            key = match.group(1).strip()
            position = match.start()
            
            # Filter out obvious non-keys (like "CPF:", "PA:" etc.)
            if not self._is_noise_word(key):
                matches.append((key, position))
        
        logger.info(f"Potential keys found: {[m[0] for m in matches]}")
        return matches
    
    def _is_noise_word(self, word: str) -> bool:
        """
        Check if a word is a common noise word that appears before colons
        but isn't a document key.
        """
        # Remove numbers and parentheses for comparison
        clean_word = re.sub(r'[0-9\(\)]', '', word).strip()
        return clean_word in self.noise_words or len(clean_word) < 3
    
    def _validate_keys(self, potential_keys: List[Tuple[str, int]]) -> List[str]:
        """
        Second pass to validate keys based on expected keys and context.
        """
        # Create a set of normalized expected keys for comparison
        normalized_expected = {self._normalize_key(k) for k in self.expected_keys}
        
        validated_keys = []
        
        for key, position in potential_keys:
            normalized = self._normalize_key(key)
            
            # Check against normalized expected keys
            if normalized in normalized_expected:
                if key not in validated_keys:
                    validated_keys.append(key)
                continue
            
            # Context validation - check if this is likely a real key
            if self._validate_by_context(key, position):
                if key not in validated_keys:
                    validated_keys.append(key)
        
        # Restore expected key order if possible
        return self._restore_key_order(validated_keys)
    
    def _normalize_key(self, key: str) -> str:
        """
        Normalize a key for comparison (strip, uppercase, remove extra spaces)
        """
        return re.sub(r'\s+', ' ', key.strip().upper())
    
    def _validate_by_context(self, key: str, position: int) -> bool:
        """
        Validate a key based on its context in the document.
        """
        # Check if key is followed by substantive content
        key_pattern = re.escape(key) + r':\s*(.+?)(?=\n\s*[A-ZÁÉÍÓÚÀÂÊÔÇÜÃÕÑ][A-ZÁÉÍÓÚÀÂÊÔÇÜÃÕÑ\s]*:|$)'
        match = re.search(key_pattern, self.texto_original[position:], re.DOTALL)
        
        if not match:
            return False
            
        content = match.group(1).strip()
        
        # If content is too short or just numbers, probably not a real key
        if len(content) < 3 or re.match(r'^[\d\s\-\.\/]+$', content):
            return False
            
        # If key appears to be part of a sentence (lowercase words before), reject it
        context_before = self.texto_original[max(0, position-30):position].strip()
        if context_before and context_before[-1].islower() and not context_before.endswith(('.', '!', '?', '\n')):
            return False
            
        return True
    
    def _restore_key_order(self, keys: List[str]) -> List[str]:
        """
        Try to restore the expected order of keys based on their appearance in the text.
        """
        # Get positions of keys in the original text
        key_positions = []
        for key in keys:
            pattern = re.escape(key) + r'\s*:'
            match = re.search(pattern, self.texto_original)
            if match:
                key_positions.append((key, match.start()))
        
        # Sort by position
        key_positions.sort(key=lambda x: x[1])
        return [k for k, _ in key_positions]
    
    def extract_key_content(self) -> Dict[str, str]:
        """
        Extract content for each validated key.
        """
        validated_keys = self.get_validated_keys()
        return self._extract_key_values(validated_keys)
    
    def _extract_key_values(self, keys: List[str]) -> Dict[str, str]:
        """
        Extract the content for each key using a more robust approach.
        """
        values = {}
        
        # Sort keys by their position in the text to handle extraction properly
        key_positions = []
        for key in keys:
            pattern = re.escape(key) + r'\s*:'
            match = re.search(pattern, self.texto_original)
            if match:
                key_positions.append((key, match.start()))
        
        # Sort by position
        key_positions.sort(key=lambda x: x[1])
        ordered_keys = [k for k, _ in key_positions]
        
        # Extract content between keys
        for i, key in enumerate(ordered_keys):
            # Find the start position (after the key and colon)
            start_pattern = re.escape(key) + r'\s*:\s*'
            start_match = re.search(start_pattern, self.texto_original)
            
            if not start_match:
                logger.warning(f"No match found for key: {key}")
                values[self._normalize_key(key).lower()] = ""
                continue
                
            start_pos = start_match.end()
            
            # Find the end position (next key or end of text)
            if i < len(ordered_keys) - 1:
                next_key = ordered_keys[i + 1]
                end_pattern = r'(?:\n\s*|\s+)' + re.escape(next_key) + r'\s*:'
                end_match = re.search(end_pattern, self.texto_original[start_pos:])
                
                if end_match:
                    end_pos = start_pos + end_match.start()
                else:
                    # If we can't find the next key, try to find a reasonable endpoint
                    end_pos = self._find_reasonable_endpoint(start_pos, key)
            else:
                # Last key, capture to a reasonable endpoint
                end_pos = self._find_reasonable_endpoint(start_pos, key)
            
            # Extract and clean the content
            content = self.texto_original[start_pos:end_pos].strip()
            content = self._clean_text(content)
            
            # Store with normalized key
            normalized_key = self._normalize_key(key).lower().replace(' ', '_')
            values[normalized_key] = content
            
        return values
    
    def _find_reasonable_endpoint(self, start_pos: int, current_key: str) -> int:
        """
        Find a reasonable endpoint for the content of a key.
        """
        # Look for patterns that might indicate the end of content
        patterns = [
            r'\n\s*[A-ZÁÉÍÓÚÀÂÊÔÇÜÃÕÑ][A-ZÁÉÍÓÚÀÂÊÔÇÜÃÕÑ\s]+:',  # Next potential key
            r'\n\s*\d+\s*(?:DOE|Quarta-feira|Segunda-feira|Terça-feira|Quinta-feira|Sexta-feira)',  # Page markers
            r'\n\s*Sessão\s+do\s+Pleno',  # Session markers
            r'\n\s*Download\s+Anexo',  # Download markers
            r'\n\s*Protocolo:',  # Protocol markers
        ]
        
        end_pos = len(self.texto_original)
        
        for pattern in patterns:
            match = re.search(pattern, self.texto_original[start_pos:])
            if match and start_pos + match.start() < end_pos:
                end_pos = start_pos + match.start()
        
        return end_pos
    
    def _clean_text(self, text: str) -> str:
        """
        Clean extracted text.
        """
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove ANSI color codes
        text = re.sub(r'\x1b\[[0-9;]*m', '', text)
        return text.strip()

# Example usage
def validate_document_keys(texto: str, expected_keys: Optional[List[str]] = None) -> Dict[str, str]:
    validator = KeyValidator(texto, expected_keys)
    return validator.extract_key_content()

# Test with a sample
if __name__ == "__main__":
    sample_text = """
    ACÓRDÃO Nº 46.771 
    PROCESSO Nº 006400.2017.2.000 
    MUNICÍPIO: ALTAMIRA 
    ÓRGÃO: FUNDO MUNICIPAL DE SAÚDE 
    EXERCÍCIO: 2017 
    ASSUNTO: CONTAS ANUAIS DE GESTÃO – PRESTAÇÃO DE CONTAS 
    ORDENADORES: WALDECIR ARANHA MAIA – 01/01/2017 a 31/01/2017 
    CPF: 055.643.792-68 
    JASON BATISTA DO COUTO – 01/02/2017 a 10/02/2017 
    CPF: 168.082.581-04 
    KÁTIA LOPES FERNANDES – 11/02/2017 a 31/12/2017 
    CPF: 278.910.462-04 
    CONTADORA: GABRIELA SOUZA ELGRABLY 
    MPC: PROCURADORA ELISABETH MASSOUD SALAME DA SILVA 
    RELATOR: CONSELHEIRO SEBASTIÃO CEZAR LEÃO COLARES 
    EMENTA: Prestação de contas de gestão. 
    DECISÃO: I – JULGAR IRREGULARES...
    """
    
    results = validate_document_keys(sample_text)
    for key, value in results.items():
        print(f"{key}: {value}")
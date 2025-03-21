import re

def extract_acordaos(text):
    """
    Extract and structure acórdãos from a DOE TCMPA document.
    
    Args:
        text (str): The full text of the DOE TCMPA document.
        
    Returns:
        list: A list of dictionaries, each containing the structured data of an acórdão.
    """
    # Find all acórdão start positions
    acordao_pattern = r'ACÓRDÃO\s+Nº\s+(\d+\.\d+)'
    acordao_matches = list(re.finditer(acordao_pattern, text))
    
    # Define section delimiters for finding the end of an acórdão
    section_delimiters = [
        "DO GABINETE DA PRESIDÊNCIA",
        "PAUTA DE JULGAMENTO",
        "DO GABINETE DE CONSELHEIRO",
        "CONTROLADORIAS DE CONTROLE EXTERNO",
        "SERVIÇOS AUXILIARES"
    ]
    
    acordaos = []
    
    for i, match in enumerate(acordao_matches):
        # Get the start position of the current acórdão
        start_pos = match.start()
        
        # Find the end position (either next acórdão or next section delimiter)
        if i < len(acordao_matches) - 1:
            end_pos = acordao_matches[i + 1].start()
        else:
            end_pos = len(text)
            for delimiter in section_delimiters:
                delimiter_pos = text.find(delimiter, start_pos)
                if delimiter_pos != -1 and delimiter_pos < end_pos:
                    end_pos = delimiter_pos
        
        # Extract the acórdão text
        acordao_text = text[start_pos:end_pos].strip()
        
        # Find where the real end of the acórdão is (often marked by "Download Anexo")
        download_pos = acordao_text.find("Download Anexo")
        if download_pos != -1:
            acordao_text = acordao_text[:download_pos].strip()
        
        # Parse the acórdão content
        acordao_data = parse_acordao(acordao_text)
        
        if acordao_data:
            acordaos.append(acordao_data)
    
    return acordaos

def parse_acordao(acordao_text):
    """
    Parse an acórdão text into a structured dictionary.
    
    Args:
        acordao_text (str): The text of a single acórdão.
        
    Returns:
        dict: A dictionary containing the structured acórdão data.
    """
    acordao = {
        "numero": None,
        "processo": None,
        "natureza": None,
        "origem": None,
        "municipio": None,
        "interessado": None,
        "responsavel": None,
        "membro_mpcm": None,
        "relatora": None,
        "ementa": None,
        "acordam": None,
        "decisao": None,
        "sessao": None,
        "texto_completo": acordao_text
    }
    
    # Extract acórdão number
    numero_match = re.search(r'ACÓRDÃO\s+Nº\s+(\d+\.\d+)', acordao_text)
    if numero_match:
        acordao["numero"] = numero_match.group(1)
    
    # Extract process information
    processo_match = re.search(r'Processo\s+(?:nº|Nº):\s+([^\n]+)', acordao_text)
    if processo_match:
        acordao["processo"] = processo_match.group(1).strip()
    
    # Extract natureza
    natureza_match = re.search(r'Natureza:\s+([^\n]+)', acordao_text)
    if natureza_match:
        acordao["natureza"] = natureza_match.group(1).strip()
    
    # Extract origem
    origem_match = re.search(r'Origem:\s+([^\n]+)', acordao_text)
    if origem_match:
        acordao["origem"] = origem_match.group(1).strip()
    
    # Extract município
    municipio_match = re.search(r'Município:\s+([^\n]+)', acordao_text)
    if municipio_match:
        acordao["municipio"] = municipio_match.group(1).strip()
    
    # Extract interessado (could be Interessado or Interessada)
    interessado_match = re.search(r'Interessad[oa]:\s+([^\n]+)', acordao_text)
    if interessado_match:
        acordao["interessado"] = interessado_match.group(1).strip()
    
    # Extract responsável
    responsavel_match = re.search(r'Responsável:\s+([^\n]+)', acordao_text)
    if responsavel_match:
        acordao["responsavel"] = responsavel_match.group(1).strip()
    
    # Extract membro MPCM
    membro_match = re.search(r'Membro[/\s]*MPCM:\s+([^\n]+)', acordao_text)
    if membro_match:
        acordao["membro_mpcm"] = membro_match.group(1).strip()
    
    # Extract relatora
    relatora_match = re.search(r'Relator[a]*:\s+([^\n]+)', acordao_text)
    if relatora_match:
        acordao["relatora"] = relatora_match.group(1).strip()
    
    # Extract ementa (everything between EMENTA: and ACORDAM)
    ementa_match = re.search(r'EMENTA:\s+([^\n]*(?:\n(?!ACORDAM).+)*)', acordao_text)
    if ementa_match:
        acordao["ementa"] = ementa_match.group(1).strip()
    
    # Extract acordam
    acordam_match = re.search(r'ACORDAM\s+([^\n]*(?:\n(?!DECISÃO).+)*)', acordao_text)
    if acordam_match:
        acordao["acordam"] = acordam_match.group(1).strip()
    
    # Extract decisão (everything between DECISÃO: and Sessão if present)
    decisao_pattern = r'DECISÃO:\s+((?:.(?!Sessão))*(?:.(?=Sessão))?.+)'
    decisao_match = re.search(decisao_pattern, acordao_text, re.DOTALL)
    if decisao_match:
        acordao["decisao"] = decisao_match.group(1).strip()
    else:
        # If the pattern fails, try a simpler approach
        if "DECISÃO:" in acordao_text:
            decisao_parts = acordao_text.split("DECISÃO:")[1]
            if "Sessão" in decisao_parts:
                acordao["decisao"] = decisao_parts.split("Sessão")[0].strip()
            else:
                acordao["decisao"] = decisao_parts.strip()
    
    # Extract session information
    sessao_match = re.search(r'Sessão\s+([^\n]+)', acordao_text)
    if sessao_match:
        acordao["sessao"] = sessao_match.group(1).strip()
    
    return acordao

def format_acordao_markdown(acordao):
    """
    Format an acordão dictionary as a markdown string.
    
    Args:
        acordao (dict): Dictionary containing acordão data.
        
    Returns:
        str: Formatted markdown string.
    """
    markdown = f"### ACÓRDÃO Nº {acordao['numero']}\n"
    
    fields = [
        ("Processo nº:", "processo"),
        ("Natureza:", "natureza"),
        ("Origem:", "origem"),
        ("Município:", "municipio"),
        ("Interessado(a):", "interessado"),
        ("Responsável:", "responsavel"),
        ("Membro MPCM:", "membro_mpcm"),
        ("Relator(a):", "relatora"),
    ]
    
    for label, key in fields:
        if acordao[key]:
            markdown += f"**{label}** {acordao[key]}  \n"
    
    if acordao["ementa"]:
        markdown += f"\n**EMENTA:** {acordao['ementa']}\n\n"
    
    if acordao["acordam"]:
        markdown += f"**ACORDAM** {acordao['acordam']}\n\n"
    
    if acordao["decisao"]:
        markdown += f"**DECISÃO:** {acordao['decisao']}\n\n"
    
    if acordao["sessao"]:
        markdown += f"{acordao['sessao']}\n"
    
    markdown += "\n---\n"
    return markdown

def extract_and_format_acordaos(text):
    """
    Extract acórdãos from text and format them as markdown.
    
    Args:
        text (str): Full text of the DOE document.
        
    Returns:
        tuple: (list of acórdão dictionaries, formatted markdown text)
    """
    acordaos = extract_acordaos(text)
    
    markdown = "# Acórdãos do Tribunal de Contas dos Municípios do Estado do Pará\n"
    markdown += "## Diário Oficial Eletrônico TCMPA\n\n"
    
    for acordao in acordaos:
        markdown += format_acordao_markdown(acordao)
    
    return acordaos, markdown

# Example usage:
if __name__ == "__main__":
    # This is a placeholder for testing - you would load your text file here
    with open("doe_tcmpa.txt", "r", encoding="utf-8") as file:
        text = file.read()
    
    acordaos, formatted_text = extract_and_format_acordaos(text)
    
    # Print number of acórdãos found
    print(f"Found {len(acordaos)} acórdãos")
    
    # Print formatted text
    print(formatted_text)
    
    # You can access individual acórdão data
    if acordaos:
        print(f"First acórdão number: {acordaos[0]['numero']}")
        print(f"First acórdão decision: {acordaos[0]['decisao'][:100]}...")
        
            def _load_known_keys(self) -> Set[str]:
        """
        Load known keys from the JSON file.
        If the file doesn't exist, create it with default keys.
        """
        default_keys = {
            "processo nº", "natureza", "origem", "município", "interessada", 
            "interessado", "responsável", "membro mpcm", "relatora", "relator", 
            "ordenador", "assunto", "exercício", "ministério público", "embargante"
        }
        
        try:
            if os.path.exists(self.known_keys_file):
                with open(self.known_keys_file, 'r', encoding='utf-8') as f:
                    return set(json.load(f))
            else:
                # Create the file with default keys if it doesn't exist
                with open(self.known_keys_file, 'w', encoding='utf-8') as f:
                    json.dump(list(default_keys), f, ensure_ascii=False, indent=2)
                return default_keys
        except Exception as e:
            logger.warning(f"Error loading known keys: {e}. Using default keys.")
            return default_keys
    
    def _save_known_keys(self):
        """Save updated known keys to the JSON file."""
        if self.new_keys_found:
            updated_keys = self.known_keys.union(self.new_keys_found)
            try:
                with open(self.known_keys_file, 'w', encoding='utf-8') as f:
                    json.dump(list(updated_keys), f, ensure_ascii=False, indent=2)
                logger.info(f"Updated known keys file with {len(self.new_keys_found)} new keys")
            except Exception as e:
                logger.error(f"Error saving known keys: {e}")

    def _extract_potential_keys(self, text: str) -> List[Dict]:
        """
        Extract all potential keys from the text using a generic pattern.
        This will find anything that looks like a key (capital letter followed by words and a colon).
        """
        # Pattern for potential keys: 
        # - Starts with capital letter
        # - Can contain letters, numbers, spaces, and "º", "ª"
        # - Ends with a colon
        # - Not preceded by an open parenthesis (to avoid matching things inside parentheses)
        pattern = r'(?<!\()[A-ZÁÉÍÓÚÀÂÊÔÇÜÃÕ][a-záéíóúàâêôçüãõA-ZÁÉÍÓÚÀÂÊÔÇÜÃÕ0-9º\s]*?:\s*'
        
        key_positions = []
        for match in re.finditer(pattern, text):
            # Extract just the key part without the colon
            key = match.group(0).rstrip(': \t')
            key_positions.append({
                'key': key,
                'start': match.start(),
                'end': match.end(),
                'is_known': key.lower() in self.known_keys
            })
            
        return key_positions
    
    def _filter_and_validate_keys(self, potential_keys: List[Dict]) -> Tuple[List[Dict], bool]:
        """
        Filter out false positives and identify new keys.
        
        Returns:
            Tuple containing:
            - List of validated key positions
            - Boolean indicating if human review is needed
        """
        # Exclude certain patterns that often lead to false matches
        excluded_patterns = [
            r'^CPF'
,      # CPF by itself
            r'^OAB'
,      # OAB by itself
            r'^CRC'
,      # CRC by itself
            r'^PA'
,       # PA by itself
            r'^SSP'
,      # SSP by itself
            r'^PC'
,       # PC by itself
            r'^Ato nº'
,   # Ato nº
            r'^art'
       # Article references
        ]
        excluded_regex = re.compile('|'.join(excluded_patterns), re.IGNORECASE)
        
        # Filter out false positives and identify new keys
        validated_keys = []
        needs_review = False
        
        for key_info in potential_keys:
            key_lower = key_info['key'].lower()
            
            # Skip if it matches an excluded pattern
            if excluded_regex.search(key_info['key']):
                continue
                
            # Check if it's a known key
            if key_lower in self.known_keys:
                key_info['is_known'] = True
                validated_keys.append(key_info)
            else:
                # This is a new key - add it but flag for review
                needs_review = True
                self.new_keys_found.add(key_lower)
                key_info['is_known'] = False
                validated_keys.append(key_info)
                logger.warning(f"New key found: {key_info['key']}")
        
        return validated_keys, needs_review

    def extract_key_value_pairs(self) -> Dict[str, str]:
        """
        Extract key-value pairs from the document with support for discovering new keys.
        """
        # First normalize the text - replace multiple spaces with a single space 
        # but preserve newlines for better key detection
        text = self.raw_text.replace('\t', ' ')
        text = re.sub(r' {2,}', ' ', text)
        
        # For key extraction, convert to single-line to simplify
        single_line_text = re.sub(r'\s+', ' ', text).strip()
        
        # Find all potential keys
        potential_keys = self._extract_potential_keys(single_line_text)
        
        # Filter and validate keys
        validated_keys, needs_review = self._filter_and_validate_keys(potential_keys)
        
        # Sort keys by position
        validated_keys.sort(key=lambda x: x['start'])
        
        # Extract values based on the positions
        result = {}
        for i, current in enumerate(validated_keys):
            next_key = validated_keys[i + 1] if i < len(validated_keys) - 1 else None
            
            value_start = current['end']
            value_end = next_key['start'] if next_key else len(single_line_text)
            
            value = single_line_text[value_start:value_end].strip()
            
            # Normalize the key (to lowercase and replace spaces with underscores)
            normalized_key = re.sub(r'\s+', '_', current['key'].lower())
            
            result[normalized_key] = value
            
            # Log extracted key-value pair
            log_level = logging.INFO if current['is_known'] else logging.WARNING
            logger.log(log_level, f"Extracted: {normalized_key} = {value}")
        
        # Add flag if the document needs review
        if needs_review:
            result["needs_review"] = True
            # Save the new keys for future use
            self._save_known_keys()
        
        return result

    def process_document(self) -> Dict[str, str]:
        """
        Process the document and return extracted key-value pairs.
        """
        return self.extract_key_value_pairs()

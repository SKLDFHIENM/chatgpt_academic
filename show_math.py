# This program is based on: https://github.com/polarwinkel/mdtex2html

from latex2mathml.converter import convert as tex2mathml
import re
from typing import List, Optional, Tuple

# HTML templates for error and warning messages
INCOMPLETE_FORMULA = '<font style="color:orange;" class="tooltip">&#9888;<span class="tooltiptext">formula incomplete</span></font>'
CONVERSION_ERROR = '<font style="color:red" class="tooltip">&#9888;<span class="tooltiptext">LaTeX-convert-error</span></font>'
BLOCK_FORMULA_TEMPLATE = '<div class="blockformula">{}</div>\n'

def convert(mdtex: str, extensions: List = None, splitParagraphs: bool = True) -> str:
    """
    Converts recursively the Markdown-LaTeX-mixture to HTML with MathML.
    
    Args:
        mdtex: The markdown text with LaTeX formulas to convert
        extensions: List of extensions to use (currently unused)
        splitParagraphs: Whether to process paragraphs separately
        
    Returns:
        HTML string with MathML for formulas
    """
    if extensions is None:
        extensions = []
        
    # Handle all paragraphs separately (prevents aftereffects)
    if splitParagraphs:
        parts = re.split("\n\n", mdtex)
        return ''.join(convert(part, extensions, splitParagraphs=False) for part in parts)
    
    # Try to find and convert different LaTeX formula formats
    formula_found, result = process_double_dollar_formula(mdtex, extensions)
    if formula_found:
        return result
        
    formula_found, result = process_single_dollar_formula(mdtex, extensions)
    if formula_found:
        return result
        
    formula_found, result = process_bracket_formula(mdtex, extensions)
    if formula_found:
        return result
        
    formula_found, result = process_parenthesis_formula(mdtex, extensions)
    if formula_found:
        return result
    
    # No formula found, return original text
    return mdtex

def process_double_dollar_formula(mdtex: str, extensions: List) -> Tuple[bool, Optional[str]]:
    """Process $$...$$ block formulas"""
    parts = re.split('\${2}', mdtex, 2)
    if len(parts) <= 1:
        return False, None
        
    # Formula found
    result = convert(parts[0], extensions, splitParagraphs=False) + '\n'
    
    try:
        result += BLOCK_FORMULA_TEMPLATE.format(tex2mathml(parts[1]))
    except Exception:
        result += BLOCK_FORMULA_TEMPLATE.format(CONVERSION_ERROR)
    
    if len(parts) == 3:
        result += convert(parts[2], extensions, splitParagraphs=False)
    else:
        result += BLOCK_FORMULA_TEMPLATE.format(INCOMPLETE_FORMULA)
        
    return True, result

def process_single_dollar_formula(mdtex: str, extensions: List) -> Tuple[bool, Optional[str]]:
    """Process $...$ inline formulas"""
    parts = re.split('\${1}', mdtex, 2)
    if len(parts) <= 1:
        return False, None
        
    # Formula found
    try:
        mathml = tex2mathml(parts[1])
    except Exception:
        mathml = CONVERSION_ERROR
    
    # Make sure textblock starts before formula
    if parts[0].endswith('\n\n') or parts[0] == '':
        parts[0] = parts[0] + '&#x200b;'
    
    if len(parts) == 3:
        result = convert(parts[0] + mathml + parts[2], extensions, splitParagraphs=False)
    else:
        result = convert(parts[0] + mathml + INCOMPLETE_FORMULA, extensions, splitParagraphs=False)
        
    return True, result

def process_bracket_formula(mdtex: str, extensions: List) -> Tuple[bool, Optional[str]]:
    """Process \[...\] block formulas"""
    parts = re.split(r'\\\[', mdtex, 1)
    if len(parts) <= 1:
        return False, None
        
    # Formula found
    result = convert(parts[0], extensions, splitParagraphs=False) + '\n'
    subparts = re.split(r'\\\]', parts[1], 1)
    
    try:
        result += BLOCK_FORMULA_TEMPLATE.format(tex2mathml(subparts[0]))
    except Exception:
        result += BLOCK_FORMULA_TEMPLATE.format(CONVERSION_ERROR)
    
    if len(subparts) == 2:
        result += convert(subparts[1], extensions, splitParagraphs=False)
    else:
        result += BLOCK_FORMULA_TEMPLATE.format(INCOMPLETE_FORMULA)
        
    return True, result

def process_parenthesis_formula(mdtex: str, extensions: List) -> Tuple[bool, Optional[str]]:
    """Process \(...\) inline formulas"""
    parts = re.split(r'\\\(', mdtex, 1)
    if len(parts) <= 1:
        return False, None
        
    # Formula found
    subparts = re.split(r'\\\)', parts[1], 1)
    
    try:
        mathml = tex2mathml(subparts[0])
    except Exception:
        mathml = CONVERSION_ERROR
    
    # Make sure textblock starts before formula
    if parts[0].endswith('\n\n') or parts[0] == '':
        parts[0] = parts[0] + '&#x200b;'
    
    if len(subparts) == 2:
        result = convert(parts[0] + mathml + subparts[1], extensions, splitParagraphs=False)
    else:
        result = convert(parts[0] + mathml + INCOMPLETE_FORMULA, extensions, splitParagraphs=False)
        
    return True, result

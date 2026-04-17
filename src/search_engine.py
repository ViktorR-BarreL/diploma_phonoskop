import re
from typing import List, Dict

class SearchEngine:
    
    def __init__(self, phonetic_map=None):
        self.phonetic_map = phonetic_map or {}
    
    def find_pattern(self, phonemes: List[Dict], pattern: str, view_mode="RU") -> List[Dict]:
        '''Ищет заданный паттерн в последовательности фонем'''
        if not phonemes or not pattern:
            return []
        
        if pattern == ".*":
            return self._find_all_phonemes(phonemes, view_mode)
        
        if pattern.startswith('['):
            return self._find_specific_sequence(phonemes, pattern, view_mode)
        else:
            return self._find_by_type(phonemes, pattern, view_mode)
    
    def _find_all_phonemes(self, phonemes: List[Dict], view_mode: str) -> List[Dict]:
        results = []
        for i, ph in enumerate(phonemes):
            label = ph['label']
            if view_mode == "RU":
                from src.gui.phonetic_map import IPA_TO_USER
                label = IPA_TO_USER.get(label, label)
            
            results.append({
                'start': ph['start'],
                'end': ph['end'],
                'pattern': '.*',
                'combination': [label],
                'indices': (i, i),
                'export': False
            })
        return results
    
    def _classify_phoneme(self, label: str) -> str:
        '''Классифицирует фонему по типу'''
        from src.gui.phonetic_map import IPA_TO_USER
        
        ru_label = IPA_TO_USER.get(label, label)
        
        # Ударные гласные
        if any(accent in ru_label for accent in ['а́', 'о́', 'у́', 'ы́', 'э́', 'и́']):
            return 'V'  # Vowel stressed
        
        # Безударные гласные
        if ru_label in ['а', 'о', 'у', 'ы', 'э', 'и']:
            return 'v'  # vowel unstressed
        
        # Всё остальное — согласные (включая мягкие с апострофом)
        return 'C'
    
    def _find_by_type(self, phonemes: List[Dict], pattern: str, view_mode: str) -> List[Dict]:
        '''Поиск по типу фонем (С, Г, Ѓ, СЃС и т.д.)'''
        types = []
        for ph in phonemes:
            ph_type = self._classify_phoneme(ph['label'])
            types.append(ph_type)
        
        search_pattern = self._pattern_to_regex(pattern)
        if not search_pattern:
            return []
        
        results = []
        type_str = ''.join(types)
        
        for match in re.finditer(search_pattern, type_str):
            start_idx = match.start()
            end_idx = match.end() - 1
            
            if start_idx >= len(phonemes) or end_idx >= len(phonemes):
                continue
            
            start_time = phonemes[start_idx]['start']
            end_time = phonemes[end_idx]['end']
            
            combination = []
            for i in range(start_idx, end_idx + 1):
                label = phonemes[i]['label']
                if view_mode == "RU":
                    from src.gui.phonetic_map import IPA_TO_USER
                    label = IPA_TO_USER.get(label, label)
                combination.append(label)
            
            results.append({
                'start': start_time,
                'end': end_time,
                'pattern': pattern,
                'combination': combination,
                'indices': (start_idx, end_idx),
                'export': False
            })
        
        return results
    
    def _find_specific_sequence(self, phonemes: List[Dict], pattern: str, view_mode: str) -> List[Dict]:
        '''Поиск конкретной последовательности фонем (например, [а́][п][а])'''
        # Извлекаем символы из скобок
        sequence = re.findall(r'\[([^\]]+)\]', pattern)
        
        if not sequence:
            return []
        
        results = []
        seq_len = len(sequence)
        
        for i in range(len(phonemes) - seq_len + 1):
            match = True
            for j, expected in enumerate(sequence):
                actual = phonemes[i + j]['label']
                if not self._matches_phoneme(actual, expected, view_mode):
                    match = False
                    break
            
            if match:
                start_time = phonemes[i]['start']
                end_time = phonemes[i + seq_len - 1]['end']
                
                combination = []
                for j in range(seq_len):
                    label = phonemes[i + j]['label']
                    if view_mode == "RU":
                        from src.gui.phonetic_map import IPA_TO_USER
                        label = IPA_TO_USER.get(label, label)
                    combination.append(label)
                
                results.append({
                    'start': start_time,
                    'end': end_time,
                    'pattern': pattern,
                    'combination': combination,
                    'indices': (i, i + seq_len - 1),
                    'export': False
                })
        
        return results
    
    def _pattern_to_regex(self, pattern: str) -> str:
        mapping = {
            'С': 'C', 
            'Г': '[Vv]',
            'Ѓ': 'V',
            'СГ': 'C[Vv]',
            'ГС': '[Vv]C',
            'СГС': 'C[Vv]C',
            'СЃ': 'CV',
            'ЃС': 'VC',
            'СЃС': 'CVC',
        }
        
        if pattern in mapping:
            return mapping[pattern]
        
        custom_map = {'С': 'C', 'Г': '[Vv]', 'Ѓ': 'V'}
        result = ''
        i = 0
        while i < len(pattern):
            if i + 1 < len(pattern) and pattern[i+1] == '+':
                result += custom_map.get(pattern[i:i+2], pattern[i:i+2])
                i += 2
            else:
                result += custom_map.get(pattern[i], pattern[i])
                i += 1
        return result
    
    def _matches_phoneme(self, actual: str, expected: str, view_mode: str) -> bool:
        from src.gui.phonetic_map import IPA_TO_USER
        
        actual_ru = IPA_TO_USER.get(actual, actual)
        
        if actual == expected or actual_ru == expected:
            return True
        
        if view_mode == "RU":
            expected_ipa = None
            from src.gui.phonetic_map import USER_TO_IPA
            if expected in USER_TO_IPA:
                expected_ipa = USER_TO_IPA[expected]
            
            if expected_ipa and actual == expected_ipa:
                return True
        
        expected_base = expected.replace('́', '')
        actual_base = actual_ru.replace('́', '')
        
        if actual_base == expected_base:
            has_expected_accent = '́' in expected
            has_actual_accent = '́' in actual_ru
            
            if has_expected_accent == has_actual_accent:
                return True
        
        if expected.endswith("'") and actual_ru == expected:
            return True
        if not expected.endswith("'") and actual_ru == expected + "'":
            return False
        
        return False
from config.logging import logger
from typing import Any
from helper.language_mapping_medical_report import replace_text_answer, replace_text_satuan, replace_text_label, replace_text_answer_custom, PRESCREENING_TEST_MAPPING, PEMFIS_TEST_MAPPING, VITAL_SIGNS_MAPPING, OTHER_LABEL_MAPPING, LAB_LABEL_MAPPING, LANGUAGE_LAB_MAPPING_SATUAN

class TranslateService: 
    def prescreening_test(self, prescreening_test: Any, language: str = "en") -> Any:
        for key, value in prescreening_test.items():
            for item in value:
                label = replace_text_label(item[0], language, PRESCREENING_TEST_MAPPING)
                new_value = replace_text_answer(item[1], language)
                new_value = replace_text_satuan(new_value, language)

                item[0] = label
                item[1] = new_value

        return prescreening_test
    
    def prescreening_test_label(self, label: str, language: str = "en") -> str:
        return replace_text_label(label, language, PRESCREENING_TEST_MAPPING)
    
    def prescreening_test_answer(self, answer: str, language: str = "en") -> str:
        new_answer = replace_text_answer(answer, language)
        new_answer = replace_text_satuan(new_answer, language)
        return new_answer
    
    def prescreening_test_satuan(self, satuan: str, language: str = "en") -> str:
        return replace_text_satuan(satuan, language)

    def pemeriksaan_fisik(self, pemeriksaan_fisik: Any, language: str = "en") -> Any:
        for item in pemeriksaan_fisik:
            label = replace_text_label(item[0], language, PEMFIS_TEST_MAPPING)
            new_value = item[1]
            if "Notes" not in label and "Catatan" not in label:
                new_value = replace_text_answer(new_value, language)
            
            item[0] = label
            item[1] = new_value

        return pemeriksaan_fisik
    
    def pemeriksaan_fisik_label(self, label: str, language: str = "en") -> str:
            return replace_text_label(label, language, PEMFIS_TEST_MAPPING)
    
    def pemeriksaan_fisik_answer(self, answer: str, language: str = "en") -> str:
        new_answer = replace_text_answer(answer, language)
        new_answer = replace_text_satuan(new_answer, language)
        return new_answer
    
    def vital_signs(self, vital_signs: Any, language: str = "en") -> Any:
        for item in vital_signs:
            label = replace_text_label(item[0], language, VITAL_SIGNS_MAPPING)
            new_value = item[1]
            if "Notes" not in label and "Catatan" not in label:
                new_value = replace_text_answer(new_value, language)
                new_value = replace_text_satuan(new_value, language)
            
            item[0] = label
            item[1] = new_value

        return vital_signs
    
    def vital_signs_label(self, label: str, language: str = "en") -> str:
        return replace_text_label(label, language, VITAL_SIGNS_MAPPING)
    
    def vital_signs_answer(self, answer: str, language: str = "en") -> str:
        new_answer = replace_text_answer(answer, language)
        new_answer = replace_text_satuan(new_answer, language)
        return new_answer
    
    def lab_label(self, label: str, language: str = "en") -> str:
        return replace_text_label(label, language, LAB_LABEL_MAPPING)
    
    def lab_answer(self, answer: str, language: str = "en") -> str:
        new_answer = replace_text_answer_custom(answer, language, LANGUAGE_LAB_MAPPING_SATUAN)
        return new_answer
    
    def other_label(self, label: str, language: str = "en") -> str:
        return replace_text_label(label, language, OTHER_LABEL_MAPPING)
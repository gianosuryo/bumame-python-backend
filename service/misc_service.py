from config.logging import logger

class MiscService:
    def calculate_bmi(self, weight_str: str, height_str: str) -> dict:
        try:
            # Convert string values and replace commas with dots
            weight_clean_str = str(weight_str).replace(",", ".").replace(" kg", "")
            height_clean_str = str(height_str).replace(",", ".").replace(" cm", "")

            if weight_clean_str == "" or height_clean_str == "":
                return {"bmi": 0, "category": ""}

            weight = float(weight_clean_str)
            height = float(height_clean_str)

            # Validate inputs
            if weight <= 0 or height <= 0:
                logger.warning("Weight or height is zero or negative")
                return {"bmi": None, "error": "Weight or height must be positive numbers"}

            # Convert height to meters and calculate BMI
            height_in_meters = height / 100
            bmi = weight / (height_in_meters * height_in_meters)
            
            # Round to 1 decimal place
            bmi = round(bmi, 1)

            # Determine BMI category
            category = ""
            if bmi < 18.5:
                category = "Underweight"
            elif 18.5 <= bmi < 23.0:
                category = "Normal" 
            elif 23.0 <= bmi <= 24.9:
                category = "Overweight"
            elif 25.0 <= bmi <= 29.9:
                category = "Obesitas Kelas 1"
            else:  # bmi >= 30
                category = "Obesitas Kelas 2"

            return {
                "bmi": bmi,
                "category": category
            }

        except Exception as e:
            logger.error(f"Error calculating BMI: {str(e)}")
            return {"bmi": None, "error": str(e)}

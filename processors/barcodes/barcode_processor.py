import cv2
from pyzbar.pyzbar import decode
import numpy as np
import os
from PIL import Image
import requests
from io import BytesIO

class BarcodeProcessor:
    def __init__(self):
        self.supported_formats = ['EAN-13', 'EAN-8', 'UPC-A', 'UPC-E', 'Code-128', 'Code-39']
    
    def process_image(self, image_path_or_url):
        """
        Process an image to detect and decode barcodes
        Args:
            image_path_or_url: Path to local image file or URL of the image
        Returns:
            list of dictionaries containing barcode information
        """
        try:
            # Load image from path or URL
            if image_path_or_url.startswith(('http://', 'https://')):
                response = requests.get(image_path_or_url)
                image = Image.open(BytesIO(response.content))
                image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            else:
                image = cv2.imread(image_path_or_url)
            
            if image is None:
                raise ValueError("Could not load image")

            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Apply thresholding to handle different lighting conditions
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Try to decode barcodes
            barcodes = decode(thresh)
            
            results = []
            for barcode in barcodes:
                # Extract barcode information
                barcode_data = barcode.data.decode('utf-8')
                barcode_type = barcode.type
                
                # Get barcode position
                (x, y, w, h) = barcode.rect
                
                # Draw rectangle around barcode
                cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)
                
                # Add barcode information to results
                results.append({
                    'data': barcode_data,
                    'type': barcode_type,
                    'position': {'x': x, 'y': y, 'width': w, 'height': h}
                })
            
            return results, image
            
        except Exception as e:
            print(f"Error processing image: {e}")
            return [], None
    
    def process_directory(self, directory_path):
        """
        Process all images in a directory
        Args:
            directory_path: Path to directory containing images
        Returns:
            Dictionary mapping image filenames to their barcode results
        """
        results = {}
        for filename in os.listdir(directory_path):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff')):
                image_path = os.path.join(directory_path, filename)
                barcodes, _ = self.process_image(image_path)
                if barcodes:
                    results[filename] = barcodes
        return results
    
    def save_processed_image(self, image, output_path):
        """
        Save processed image with barcode rectangles
        Args:
            image: Processed image with rectangles
            output_path: Path to save the image
        """
        cv2.imwrite(output_path, image)

def main():
    # Example usage
    processor = BarcodeProcessor()
    
    # Process a single image
    image_path = "path/to/your/image.jpg"
    barcodes, processed_image = processor.process_image(image_path)
    
    if barcodes:
        print("Found barcodes:")
        for barcode in barcodes:
            print(f"Type: {barcode['type']}, Data: {barcode['data']}")
        
        # Save processed image with rectangles
        processor.save_processed_image(processed_image, "processed_image.jpg")
    else:
        print("No barcodes found")

if __name__ == "__main__":
    main() 
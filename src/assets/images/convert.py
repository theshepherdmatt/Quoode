import os
import sys
import cairosvg
from PIL import Image

def batch_convert_svg_to_png(input_directory, output_directory, size=35):
    # Ensure the output directory exists
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)
    
    # List all SVG files in the input directory
    for filename in os.listdir(input_directory):
        if filename.endswith(".svg"):
            input_path = os.path.join(input_directory, filename)
            output_filename = os.path.splitext(filename)[0] + ".png"
            output_path = os.path.join(output_directory, output_filename)

            try:
                # Convert SVG to PNG
                cairosvg.svg2png(url=input_path, write_to=output_path)
                
                # Load PNG image and resize
                with Image.open(output_path) as png_image:
                    resized_image = png_image.resize((size, size), Image.ANTIALIAS)
                    resized_image.save(output_path, format="PNG")

                print(f"Successfully converted and resized: {input_path} -> {output_path}")
            except Exception as e:
                print(f"Error converting {input_path}: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python batch_convert_svg_to_png.py <input_directory> <output_directory> [size]")
        print("Example: python batch_convert_svg_to_png.py ./svgs ./pngs 35")
    else:
        input_dir = sys.argv[1]
        output_dir = sys.argv[2]
        size = int(sys.argv[3]) if len(sys.argv) > 3 else 35

        batch_convert_svg_to_png(input_dir, output_dir, size)


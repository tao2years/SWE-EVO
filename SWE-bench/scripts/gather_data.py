import os
import glob
import argparse
import json
import yaml
from datasets import Dataset, DatasetDict


def load_files(input_dir, file_format):
    """Load files from input directory based on specified format."""
    if file_format.lower() == 'yaml':
        pattern = '*.yaml'
        loader_func = yaml.safe_load
    elif file_format.lower() == 'json':
        pattern = '*.json'
        loader_func = json.load
    else:
        raise ValueError(f"Unsupported file format: {file_format}. Supported formats: yaml, json")
    
    files = glob.glob(os.path.join(input_dir, pattern))
    data = []
    for file_path in files:
        with open(file_path, 'r', encoding='utf-8') as f:
            # Each file is a single document
            doc = loader_func(f)
            doc['version'] = ''
            doc['hints_text'] = ''
            data.append(doc)
    return data


def main():
    parser = argparse.ArgumentParser(description='Export YAML or JSON files as a HuggingFace dataset.')
    parser.add_argument('--input_dir', type=str, default='output', help='Directory containing input files')
    parser.add_argument('--output_dir', type=str, required=True, help='Directory to save the HuggingFace dataset (required)')
    parser.add_argument('--format', type=str, choices=['yaml', 'json'], default='json', 
                       help='Input file format (default: json)')
    args = parser.parse_args()

    data = load_files(args.input_dir, args.format)
    if not data:
        print(f'No {args.format.upper()} files found in {args.input_dir}')
        return

    dataset = Dataset.from_list(data)
    print(f'Loaded {len(dataset)} records from {args.input_dir}')

    dataset = DatasetDict({'test': dataset})

    os.makedirs(args.output_dir, exist_ok=True)
    dataset.save_to_disk(args.output_dir)
    print(f'Dataset saved to {args.output_dir} using HuggingFace save_to_disk.')


if __name__ == '__main__':
    main()

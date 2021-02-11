import argparse, os
from corona.analysis.analysis_pipeline import run_analysis_pipeline


def is_valid_uuid(uuid):
    '''UUid is alphanumeric string of len 32'''
    return len(uuid) == 32 and uuid.isalnum()


# Read command line arguments
parser = argparse.ArgumentParser(description='Run risk analysis for a specific patient.')
parser.add_argument('-p', '--patient', required=True, help='patient uuid', nargs='+')

# Run the analysis pipeline
args = parser.parse_args()

for uuid in args.patient:
    if is_valid_uuid(uuid):
        run_analysis_pipeline(uuid, output_formats = ['html'],
                              include_maps="interactive")

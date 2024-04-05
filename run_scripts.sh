# DIRPATH='dataset/Mar28'

# Run flask script
# python3 flask_prep_pi_dynamoDB.py -d $DIRPATH

# # Run transcription script
# terminator -e "python3 transcribe_chunk_pi.py -d $DIRPATH; exec bash"

# # Run record script
# terminator -e "python3 record_DOA_ID_chunks_pi.py -d $DIRPATH; exec bash"

gnome-terminal --tab -- bash -ic "source transcribe.sh; exec bash"
gnome-terminal --tab -- bash -ic "source flask.sh; exec bash"
gnome-terminal --tab -- bash -ic "source record.sh; exec bash"
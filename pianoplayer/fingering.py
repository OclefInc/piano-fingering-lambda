import os
import tempfile
from music21 import converter
from pianoplayer.hand import Hand
from pianoplayer.scorereader import reader
from pianoplayer.core import annotate_fingers_xml

class FingeringGenerator:
    def __init__(self, file_path, hand_size='M', verbose=False, args=None):
        """
        Initialize a FingeringGenerator to add fingerings to a music score

        Args:
            file_path (str): Path to the input music file
            hand_size (str): Hand size (XXS, XS, S, M, L, XL, XXL)
            verbose (bool): Whether to print detailed information
            args: Optional args with rbeam and lbeam attributes for hand part indices
        """
        self.file_path = file_path
        self.hand_size = hand_size
        self.verbose = verbose
        self.args = args

    def process(self):
        """
        Process the music file and add fingerings

        Returns:
            str: Path to the processed output file
        """
        # Create a temporary output file
        output_file = tempfile.NamedTemporaryFile(suffix='.musicxml', delete=False)
        output_path = output_file.name
        output_file.close()

        # Parse the input score
        sf = converter.parse(self.file_path)

        # Get beam indices for right and left hands
        rbeam = 0  # Default right hand beam
        lbeam = 1  # Default left hand beam

        if self.args is not None:
            if hasattr(self.args, 'rbeam'):
                rbeam = self.args.rbeam
            if hasattr(self.args, 'lbeam'):
                lbeam = self.args.lbeam

        # Setup right hand
        rh = Hand("right", self.hand_size)
        rh.verbose = self.verbose
        rh.autodepth = True
        rh.lyrics = False

        # Setup left hand
        lh = Hand("left", self.hand_size)
        lh.verbose = self.verbose
        lh.autodepth = True
        lh.lyrics = False

        # Process right hand with specified beam
        rh.noteseq = reader(sf, beam=rbeam)
        rh.generate()

        # Process left hand with specified beam
        lh.noteseq = reader(sf, beam=lbeam)
        lh.generate()

        # Annotate the score with fingerings, passing the args
        sf = annotate_fingers_xml(sf, rh, args=self.args, is_right=True)
        sf = annotate_fingers_xml(sf, lh, args=self.args, is_right=False)

        # Write the annotated score to file
        sf.write('xml', fp=output_path)

        return output_path
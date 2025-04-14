#-------------------------------------------------------------------------------
# Name:         PianoPlayer
# Purpose:      Find optimal fingering for piano scores
# Author:       Marco Musy
#-------------------------------------------------------------------------------
from music21.articulations import Fingering
import pianoplayer.utils as utils


#####################################################
class Hand:
    def __init__(self, side="right", size='M'):

        self.LR        = side
        # fingers pos at rest first is dummy, (cm), asymmetry helps with scales
        self.frest     = [None,  -7.0,-2.8, 0.0, 2.8, 5.6]
        self.weights   = [None,   1.1, 1.0, 1.1, 0.9, 0.8] # finger relative strength
        self.bfactor   = [None,   0.3, 1.0, 1.1, 0.8, 0.7] # hit of black key bias
        self.noteseq   = []
        self.fingerseq = []
        self.depth     = 9
        self.autodepth = True
        self.verbose   = False
        self.lyrics    = False  # show fingering numbers as lyrics in musescore
        self.size      = size

        self.hf = utils.handSizeFactor(size)
        for i in (1,2,3,4,5):
            if self.frest[i]: self.frest[i] *= self.hf
        print('Your hand span set to size-'+size, 'which is', 21*self.hf, 'cm')
        print('(max relaxed distance between thumb and pinkie)')
        self.cfps = list(self.frest) # hold current finger positions


    #####################################################
    def set_fingers_positions(self, fings, notes, i):

        fi = fings[i]
        ni = notes[i]
        ifx = self.frest[fi]
        if ifx is not None:
            for j in (1,2,3,4,5):
                jfx = self.frest[j]
                self.cfps[j] = (jfx-ifx) + ni.x


    #####################################################
    def ave_velocity(self, fingering, notes):
        ###calculate v for playing for notes in a given fingering combination

        self.set_fingers_positions(fingering, notes, 0)  #init fingers position

        vmean = 0.
        for i in range(1, self.depth):
            na = notes[i-1]
            nb = notes[i]
            fb = fingering[i]
            dx = abs(nb.x - self.cfps[fb])   # space travelled by finger fb
            dt = abs(nb.time - na.time) +0.1 # available time +smoothing term 0.1s
            v  = dx/dt                       # velocity
            if nb.isBlack:                   # penalty (by increasing speed)
                v /= self.weights[fb] * self.bfactor[fb]
            else:
                v /= self.weights[fb]
            vmean += v
            self.set_fingers_positions(fingering, notes, i) #update all fingers

        return vmean / (self.depth-1)


    #####################################################
    def optimize_seq(self, nseq, istart):
        '''Generate meaningful fingering for a note sequence of size depth'''

        #---------------------------------------------------------
        def skip(fa,fb, na,nb, level):
            ### two-consecutive-notes movement, skipping rules ###
            # fa is fingering for note na, level is passed only for debugging

            xba = nb.x - na.x  # physical distance btw the second to first note, in cm

            if not na.isChord and not nb.isChord: # neither of the 2 notes live in a chord
                if fa==fb and xba and na.duration<4:
                    return True # play different notes w/ same finger, skip
                if fa>1 : # if a is not thumb
                    if fb>1 and (fb-fa)*xba<0: return True # non-thumb fingers are crossings, skip
                    if fb==1 and nb.isBlack and xba>0: return True # crossing thumb goes to black, skip
                else: # a is played by thumb:
                    # skip if  a is black  and  b is behind a  and  fb not thumb  and na.duration<2:
                    if na.isBlack and xba<0 and fb>1 and na.duration<2: return True

            elif na.isChord and nb.isChord and na.chordID == nb.chordID:
                # na and nb are notes in the same chord
                if fa==fb: return True   # play different chord notes w/ same finger, skip
                if fa<fb and self.LR=='left' : return True
                if fa>fb and self.LR=='right': return True
                axba = abs(xba)*self.hf /0.8
                # max normalized distance in cm btw 2 consecutive fingers
                if axba> 5 and (fa==3 and fb==4 or fa==4 and fb==3): return True
                if axba> 5 and (fa==4 and fb==5 or fa==5 and fb==4): return True
                if axba> 6 and (fa==2 and fb==3 or fa==3 and fb==2): return True
                if axba> 7 and (fa==2 and fb==4 or fa==4 and fb==2): return True
                if axba> 8 and (fa==3 and fb==5 or fa==5 and fb==3): return True
                if axba>11 and (fa==2 and fb==5 or fa==5 and fb==2): return True
                if axba>12 and (fa==1 and fb==2 or fa==2 and fb==1): return True
                if axba>14 and (fa==1 and fb==3 or fa==3 and fb==1): return True
                if axba>16 and (fa==1 and fb==4 or fa==4 and fb==1): return True

            return False
        #---------------------------------------------------------------------------

        if self.autodepth:
            #choose depth based on time span of 3.5 seconds
            if nseq[0].isChord:
                self.depth = max(3, nseq[0].NinChord - nseq[0].chordnr + 1)
            else:
                tn0 = nseq[0].time
                for i in (4,5,6,7,8,9):
                    self.depth = i
                    if nseq[i-1].time - tn0 > 3.5:
                        break
        depth = self.depth

        fingers = (1,2,3,4,5)
        n1, n2, n3, n4, n5, n6, n7, n8, n9 = nseq
        u_start = [istart]
        if istart == 0:
            u_start = fingers

        #####################################
        out = ([0 for i in range(depth)], -1)
        minvel = 1.e+10
        for f1 in u_start:
            for f2 in fingers:
                if skip(f1,f2, n1,n2, 2): continue
                for f3 in fingers:
                    if f3 and skip(f2,f3, n2,n3, 3): continue
                    if depth<4: u=[False]
                    else:       u=fingers
                    for f4 in u:
                        if f4 and skip(f3,f4, n3,n4, 4): continue
                        if depth<5: u=[False]
                        else:       u=fingers
                        for f5 in u:
                            if f5 and skip(f4,f5, n4,n5, 5): continue
                            if depth<6: u=[False]
                            else:       u=fingers
                            for f6 in u:
                                if f6 and skip(f5,f6, n5,n6, 6): continue
                                if depth<7: u=[False]
                                else:       u=fingers
                                for f7 in u:
                                    if f7 and skip(f6,f7, n6,n7, 7): continue
                                    if depth<8: u=[False]
                                    else:       u=fingers
                                    for f8 in u:
                                        if f8 and skip(f7,f8, n7,n8, 8): continue
                                        if depth<9: u=[False]
                                        else:       u=fingers
                                        for f9 in u:
                                            if f9 and skip(f8,f9, n8,n9, 9): continue
                                            c = [f1,f2,f3,f4,f5,f6,f7,f8,f9]
                                            v = self.ave_velocity(c, nseq)
                                            if v < minvel:
                                                out = (c, v)
                                                minvel  = v
        # if out[1]==-1: exit() #no combination found
        return out

    def copy_note(self, note):
        """Create a proper copy of a note object to avoid reference issues"""
        import copy

        # Create a shallow copy of the note
        note_copy = copy.copy(note)

        # For critical music21 objects, create new references
        if hasattr(note, 'note21') and note.note21 is not None:
            note_copy.note21 = copy.copy(note.note21)

        if hasattr(note, 'chord21') and note.chord21 is not None:
            note_copy.chord21 = copy.copy(note.chord21)

        return note_copy


    ###########################################################################################
    def generate(self, start_measure=0, nmeasures=1000):

        if start_measure == 1:
            start_measure=0 # avoid confusion with python numbering

        if self.LR == "left":
            for anote in self.noteseq:
                anote.x = -anote.x     # play left as a right on a mirrored keyboard

        # Store the original sequence length
        original_noteseq = self.noteseq
        original_length = len(original_noteseq)

        # Add padding at the end with copies of last few notes
        if original_length >= 9:  # Only add padding if we have enough notes
            padding_size = 9  # Same as the window size
            padding_notes = []

            # Create copies of the last notes
            for i in range(padding_size):
                # Get the source note from the end
                source_idx = original_length - padding_size + i
                if source_idx >= 0 and source_idx < original_length:
                    # Create a proper copy of the note
                    note_copy = self.copy_note(original_noteseq[source_idx])
                    # Mark as padding
                    note_copy.is_padding = True
                    padding_notes.append(note_copy)

            # Append padding to sequence
            self.noteseq = original_noteseq + padding_notes

        start_finger, out, vel = 0, [0 for i in range(9)], 0
        N = len(self.noteseq)
        if self.depth < 3: self.depth = 3
        if self.depth > 9: self.depth = 9

        # Track the current measure for progress reporting
        current_measure = start_measure
        last_reported_measure = start_measure - 1

        # Process all notes (but only apply fingerings to original notes)
        for i in range(original_length):  # Only process original note indices
            an = self.noteseq[i]
            if an.measure:
                if an.measure < start_measure: continue
                if an.measure > start_measure + nmeasures: break

                # Report progress when measure changes
                if an.measure != last_reported_measure:
                    current_measure = an.measure
                    last_reported_measure = current_measure

            # Always use full window size since we have padding
            ninenotes = self.noteseq[i:i+9]
            out, vel = self.optimize_seq(ninenotes, start_finger)
            best_finger = out[0]
            start_finger = out[1]

            an.fingering = best_finger
            self.set_fingers_positions(out, ninenotes, 0)
            self.fingerseq.append(list(self.cfps))

            # Apply fingering to note
            if best_finger > 0:
                fng = Fingering(best_finger)
                if an.isChord:
                    if len(an.chord21.pitches) < 4:
                        # dont show fingering in the lyrics line for >3 note-chords
                        if self.lyrics:
                            nl = len(an.chord21.pitches) - an.chordnr
                            an.chord21.addLyric(best_finger, nl)
                        else:
                            an.chord21.articulations.append(fng)
                else:
                    if self.lyrics:
                        an.note21.addLyric(best_finger)
                    else:
                        an.note21.articulations.append(fng)

            # Print info if verbose
            # if self.verbose:
            #     if not best_finger: best_finger = '?'
            #     if an.measure: print(f"meas.{an.measure: <3}", end=' ')
            #     print(f"finger_{best_finger}  plays  {an.name: >2}{an.octave}", end=' ')
            #     print(f"  v={round(vel,1)}", end='')
            #     if self.autodepth:
            #         print("\t "+str(out[0:self.depth]) + " d:" + str(self.depth))
            #     else:
            #         print("\t"+("   "*(i%self.depth))+str(out[0:self.depth]))
            # else:
            #     if i and not i%100 and an.measure:
            #         print('scanned', i, '/', original_length,
            #             'notes, measure', an.measure+1, ' for the', self.LR ,'hand...')

        # Final verification pass
        for i in range(original_length-1, -1, -1):
            an = self.noteseq[i]
            if an.measure and start_measure <= an.measure <= start_measure + nmeasures:
                if an.fingering == 0:  # Missing fingering
                    # Find the nearest note with valid fingering
                    nearest_finger = None
                    # Look backward first
                    for j in range(i-1, -1, -1):
                        if j < original_length and self.noteseq[j].fingering > 0:
                            nearest_finger = self.noteseq[j].fingering
                            break

                    # If not found backward, look forward
                    if nearest_finger is None:
                        for j in range(i+1, original_length):
                            if self.noteseq[j].fingering > 0:
                                nearest_finger = self.noteseq[j].fingering
                                break

                    # Default to middle finger if still not found
                    if nearest_finger is None:
                        nearest_finger = 3

                    # Assign fingering
                    an.fingering = nearest_finger

                    # Apply the fingering to the music21 object
                    fng = Fingering(an.fingering)
                    if an.isChord:
                        if len(an.chord21.pitches) < 4:
                            if self.lyrics:
                                nl = len(an.chord21.pitches) - an.chordnr
                                an.chord21.addLyric(an.fingering, nl)
                            else:
                                an.chord21.articulations.append(fng)
                    else:
                        if self.lyrics:
                            an.note21.addLyric(an.fingering)
                        else:
                            an.note21.articulations.append(fng)

                    if self.verbose:
                        print(f"Fixed missing fingering in measure {an.measure}: {an.name}{an.octave} -> finger_{an.fingering} (filled)")

        # Restore the original sequence (remove padding)
        self.noteseq = original_noteseq

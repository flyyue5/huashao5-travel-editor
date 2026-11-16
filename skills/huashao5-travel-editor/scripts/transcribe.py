#!/usr/bin/env python3
"""Optional local ASR adapter. Output is an unverified draft; never a speaker identity."""
import argparse
from pathlib import Path
import sys
from travel_edit import write


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('audio');p.add_argument('output');p.add_argument('--model',default='small')
    p.add_argument('--language',default='zh');p.add_argument('--device',default='cpu',choices=['cpu','cuda'])
    p.add_argument('--local-files-only',action='store_true');p.add_argument('--model-cache')
    a=p.parse_args()
    if Path(a.output).exists():p.error('Output exists; choose a new draft filename.')
    if not Path(a.audio).is_file():p.error('Audio file not found.')
    try:from faster_whisper import WhisperModel
    except ImportError:p.error('Install optional requirements-asr.txt, or use a transcript from another tool.')
    try:
        model=WhisperModel(a.model,device=a.device,compute_type='int8' if a.device=='cpu' else 'float16',
            download_root=a.model_cache,local_files_only=a.local_files_only)
        segments,info=model.transcribe(a.audio,language=a.language,word_timestamps=True,vad_filter=True,
            condition_on_previous_text=False)
        records=[{'start':s.start,'end':s.end,'text':s.text.strip(),'text_verified':False,
            'words':[{'start':w.start,'end':w.end,'word':w.word,'probability':w.probability} for w in s.words or []]} for s in segments]
        write(a.output,{'source_filename':Path(a.audio).name,'language':info.language,'speaker_identity_inferred':False,
            'review_status':'unverified_asr_draft','segments':records})
        print(f'Saved {len(records)} draft segments; listen and correct before adding to EDL.')
    except Exception as e:print(f'ERROR: ASR failed: {e}',file=sys.stderr);return 2
    return 0


if __name__=='__main__':sys.exit(main())

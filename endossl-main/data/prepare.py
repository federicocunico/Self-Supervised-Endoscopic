'''
Author: Tong Yu
Copyright (c) University of Strasbourg. All Rights Reserved.
'''

import json
from tqdm import tqdm
import argparse
import requests
import hashlib
import tarfile
import os


URL = "https://s3.unistra.fr/camma_public/datasets/cholec80/cholec80.tar.gz"
CHUNK_SIZE = 2 ** 20

parser = argparse.ArgumentParser()
parser.add_argument("--data_rootdir", default='/home/royhirsch/research-il-lapmsn/cholec80')
parser.add_argument("--verify_checksum", action="store_true")
parser.add_argument("--keep_archive", action="store_true")
args = parser.parse_args()

outfile = os.path.join(args.data_rootdir, "cholec80.tar.gz")
outdir = os.path.join(args.data_rootdir, "cholec80")
curr_dir = os.path.dirname(os.path.realpath(__file__))
config_path = os.path.join(curr_dir, 'config.json')

# Download
print("Downloading archive to {}".format(outfile))
with requests.get(URL, stream=True) as r:
  r.raise_for_status()
  total_length = int(float(r.headers.get("content-length")) / 10 ** 6)
  progress_bar = tqdm(unit="MB", total=total_length, ncols=150)
  with open(outfile, "wb") as f:
    for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
      progress_bar.update(len(chunk) / 10 ** 6)
      f.write(chunk)

# Optional checksum verification
if args.verify_checksum:
  print("Verifying checksum")
  m = hashlib.md5()
  with open(outfile, 'rb') as f:
    while True:
      data = f.read(CHUNK_SIZE)
      if not data:
        break
      m.update(data)
  chk = m.hexdigest()
  with open("checksum.txt") as f:
    true_chk = f.read()
  print("Checksum: {}".format(chk))
  assert(m.hexdigest() == chk)

# Extraction
print("Extracting files to {}".format(outdir))
with tarfile.open(outfile, "r") as t:
  t.extractall(outdir)

# Cleanup
if not args.keep_archive:
  os.remove(outfile)

# Config setup
with open(config_path, "r") as f:
  config = json.loads(f.read())

config["cholec80_dir"] = outdir
json_string = json.dumps(config, indent=2, sort_keys=True)

with open(config_path, "w") as f:
  f.write(json_string)

print("All done - config saved to {}".format(
  os.path.join(os.getcwd(), "config.json"))
)
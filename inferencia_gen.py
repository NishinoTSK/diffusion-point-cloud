import os
import time
import math
import argparse
import torch
from tqdm.auto import tqdm

from utils.dataset import *
from utils.misc import *
from utils.data import *
from models.vae_gaussian import *
from models.vae_flow import *
from models.flow import add_spectral_norm, spectral_norm_power_iteration
from evaluation import *

def normalize_point_clouds(pcs, mode, logger):
    if mode is None:
        logger.info('Will not normalize point clouds.')
        return pcs
    logger.info('Normalization mode: %s' % mode)
    for i in tqdm(range(pcs.size(0)), desc='Normalize'):
        pc = pcs[i]
        if mode == 'shape_unit':
            shift = pc.mean(dim=0).reshape(1, 3)
            scale = pc.flatten().std().reshape(1, 1)
        elif mode == 'shape_bbox':
            pc_max, _ = pc.max(dim=0, keepdim=True) # (1, 3)
            pc_min, _ = pc.min(dim=0, keepdim=True) # (1, 3)
            shift = ((pc_min + pc_max) / 2).view(1, 3)
            scale = (pc_max - pc_min).max().reshape(1, 1) / 2
        pc = (pc - shift) / scale
        pcs[i] = pc
    return pcs


# Arguments
parser = argparse.ArgumentParser()
parser.add_argument('--ckpt', type=str, default='')
parser.add_argument('--categories', type=str_list, default=['airplane'])
parser.add_argument('--save_dir', type=str, default='./results')
parser.add_argument('--device', type=str, default='cuda')
# Datasets and loaders
parser.add_argument('--dataset_path', type=str, default='/content/agora.h5')
parser.add_argument('--batch_size', type=int, default=128)
# Sampling
parser.add_argument('--sample_num_points', type=int, default=1024)
parser.add_argument('--normalize', type=str, default='shape_bbox', choices=[None, 'shape_unit', 'shape_bbox'])
parser.add_argument('--seed', type=int, default=9)
args = parser.parse_args()


# Logging
save_dir = os.path.join(args.save_dir, 'GEN_Ours_%s_%d' % ('_'.join(args.categories), int(time.time())) )
if not os.path.exists(save_dir):
    os.makedirs(save_dir)
logger = get_logger('test', save_dir)
for k, v in vars(args).items():
    logger.info('[ARGS::%s] %s' % (k, repr(v)))

# Checkpoint
ckpt = torch.load(args.ckpt,weights_only=False)
seed_all(args.seed)

# Datasets and loaders
# logger.info('Loading datasets...')
# test_dset = ShapeNetCore(
#     path=args.dataset_path,
#     cates=args.categories,
#     split='test',
#     scale_mode=args.normalize,
# )
# test_loader = DataLoader(test_dset, batch_size=args.batch_size, num_workers=0)

# Model
# logger.info('Loading model...')
if ckpt['args'].model == 'gaussian':
    model = GaussianVAE(ckpt['args']).to(args.device)
elif ckpt['args'].model == 'flow':
    model = FlowVAE(ckpt['args']).to(args.device)
# logger.info(repr(model))
# if ckpt['args'].spectral_norm:
#     add_spectral_norm(model, logger=logger)
model.load_state_dict(ckpt['state_dict'])

# Reference Point Clouds
# ref_pcs = []
# for i, data in enumerate(test_dset):
#     ref_pcs.append(data['pointcloud'].unsqueeze(0))
# ref_pcs = torch.cat(ref_pcs, dim=0)

# Generate Point Clouds
gen_pcs = []
auxiliar = 0
while auxiliar < 5:
  with torch.no_grad():
      z = torch.randn([args.batch_size, ckpt['args'].latent_dim]).to(args.device)
      x = model.sample(z, args.sample_num_points, flexibility=ckpt['args'].flexibility)
      gen_pcs.append(x.detach().cpu())
      auxiliar = auxiliar + 1
gen_pcs = torch.cat(gen_pcs, dim=0)[:auxiliar]
if args.normalize is not None:
    gen_pcs = normalize_point_clouds(gen_pcs, mode=args.normalize, logger=logger)

# Save
# logger.info('Saving point clouds...')
np.save(os.path.join(save_dir, 'inferencia.npy'), gen_pcs.numpy())

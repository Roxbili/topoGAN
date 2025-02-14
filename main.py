#!/usr/bin/python
# -*- coding: utf8 -*-
"""
Main function of topoGAN framework 
for jointly predicting multiple target brain graphs from a single source graph.

The original paper can be found in: https://www.sciencedirect.com
Alaa Bessadok, Mohamed Ali Mahjoub, and Islem Rekik. "Brain Multigraph Prediction using Topology-Aware Adversarial Graph Neural Network",
Medical Image Analysis Journal 2020.
---------------------------------------------------------------------

TopoGAN(src_loader, tgt_loaders, nb_clusters, opts)
          Inputs:
                  src_loader:   a PyTorch dataloader returning elements from source dataset batch by batch
                  tgt_loaders:  a PyTorch dataloader returning elements from target dataset batch by batch
                  nb_clusters:  number of clusters used to cluster the source graph embeddings
                  opts:         a python object (parser) storing all arguments needed to run the code such as hyper-parameters 
          Output:
                  model:        our TopoGAN model
                  
Sample use for training:
  model = TopoGAN(src_loader, tgt_loaders, opts.nb_clusters, opts)
  model.train()

Sample use for testing:
  model = TopoGAN(src_loader, tgt_loaders, opts.nb_clusters, opts)
  predicted_target_graphs, source_graphs = model.test()
          Output:
                  predicted_target_graphs : a list of size num_domains-1 where num_domains is the number of source and target domains.
                                           Each element is an (n × f) matrix stacking the predicted target feature graphs f of n testing subjects
                  source_graphs : a matrix of size (n × f) stacking the source feature graphs f of n testing subjects
---------------------------------------------------------------------
Copyright 2021 Alaa Bessadok, Sousse University.
Please cite the above paper if you use this code.
All rights reserved.
"""
import os, sys
import argparse
import random
import yaml
import numpy as np
import pandas as pd
from torch.backends import cudnn
from prediction import TopoGAN
from data_loader import *

parser = argparse.ArgumentParser()
# initialisation
# Basic opts.
parser.add_argument('--num_domains', type=int, default=2, help='how many domains(including source domain)')
parser.add_argument('--num_subjects', type=int, default=300, help='how many subjects')
parser.add_argument('--src_feature_len', type=int, default=1200, help='the length of the source feature')
parser.add_argument('--tgt_feature_len', type=int, default=1200, help='the length of the target feature')
parser.add_argument('--mode', type=str, default='train', choices=['train', 'test'])
parser.add_argument('--log_dir', type=str, default='logs/')
parser.add_argument('--checkpoint_dir', type=str, default='models/')
parser.add_argument('--sample_dir', type=str, default='samples/')
parser.add_argument('--result_dir', type=str, default='results/')
parser.add_argument('--result_root', type=str, default='result_TopoGAN/')

# GCN model opts
parser.add_argument('--hidden1', type=int, default=32)
parser.add_argument('--hidden2', type=int, default=16)
parser.add_argument('--dropout', type=float, default=0.5)
parser.add_argument('--in_feature', type=int, default=1200)

# Discriminator model opts.
parser.add_argument('--cls_loss', type=str, default='BCE', choices=['LS','BCE'], help='least square loss or binary cross entropy loss')
parser.add_argument('--lambda_cls', type=float, default=1, help='hyper-parameter for domain classification loss')
parser.add_argument('--Lf', type=float, default=5, help='a constant with respect to the inter-domain constraint')
parser.add_argument('--lambda_reg', type=float, default=0.1, help='a constant with respect to the gradient penalty')

# Generator model opts.
parser.add_argument('--lambda_idt', type=float, default=10, help='hyper-parameter for identity loss')
parser.add_argument('--lambda_info', type=float, default=1, help='hype-rparameter for information maximazation loss')
parser.add_argument('--lambda_topology', type=float, default=0.1, help='hyper-parameter for topological constraint')
parser.add_argument('--nb_clusters', type=int, default=2, help='number of clusters for MKML clustering')

# Training opts.
parser.add_argument('--batch_size', type=int, default=62, help='mini-batch size')
parser.add_argument('--num_iters', type=int, default=10, help='number of total iterations for training D')
parser.add_argument('--g_lr', type=float, default=0.0001, help='learning rate for G')
parser.add_argument('--d_lr', type=float, default=0.0001, help='learning rate for D')
parser.add_argument('--n_critic', type=int, default=5, help='number of D updates per each G update')
parser.add_argument('--beta1', type=float, default=0.5, help='beta1 for Adam optimizer')
parser.add_argument('--beta2', type=float, default=0.999, help='beta2 for Adam optimizer')
parser.add_argument('--resume_iters', type=int, default=None, help='resume training from this step')
parser.add_argument('--num_workers', type=int, default=1, help='num_workers to load data.')
parser.add_argument('--log_step', type=int, default=5)
parser.add_argument('--sample_step', type=int, default=5)
parser.add_argument('--model_save_step', type=int, default=10)

# Test opts.
parser.add_argument('--test_iters', type=int, default=10, help='test model from this step')

opts = parser.parse_args()
opts.log_dir = os.path.join(opts.result_root, opts.log_dir)
opts.checkpoint_dir = os.path.join(opts.result_root, opts.checkpoint_dir)
opts.sample_dir = os.path.join(opts.result_root, opts.sample_dir)
opts.result_dir = os.path.join(opts.result_root, opts.result_dir)


if __name__ == '__main__':

    # For fast training.
    cudnn.benchmark = True

    if opts.mode == 'train':
        """
        Training topoGAN
        """
        # Create directories if not exist.
        create_dirs_if_not_exist([opts.log_dir, opts.checkpoint_dir, opts.sample_dir, opts.result_dir])
        
        # log opts.
        with open(os.path.join(opts.result_root, 'opts.yaml'), 'w') as f:
            f.write(yaml.dump(vars(opts)))

        #################### data generate #####################
        # # Simulate graph data for easy test the code
        # source_target_domains = []
        # for i in range(opts.num_domains):
        #   source_target_domains.append(np.random.normal(random.random(), random.random(), (280,595)))
        
        # # Choose the source domain to be translated
        # src_domain = 0
        
        # # Load source and target TRAIN datasets
        # tgt_loaders = []
        # for domain in range(0, opts.num_domains):
        #     if domain == src_domain:
        #         source_feature = source_target_domains[domain]
        #         # print(source_feature.shape) # (70, 595)
        #         src_loader = get_loader(source_feature, opts.batch_size, opts.num_workers)
        #     else:
        #         target_feature = source_target_domains[domain]
        #         tgt_loader = get_loader(target_feature, opts.batch_size, opts.num_workers)
        #         tgt_loaders.append(tgt_loader)

        src_data = np.random.rand(opts.num_subjects * opts.batch_size, opts.src_feature_len)
        src_loader = get_loader(src_data, opts.batch_size, opts.num_workers)
        tgt_data = np.random.rand(opts.num_subjects * opts.batch_size, opts.tgt_feature_len)
        tgt_loader = get_loader(tgt_data, opts.batch_size, opts.num_workers)
        tgt_loaders = [tgt_loader]

        # Train TopoGAN
        model = TopoGAN(src_loader, tgt_loaders, opts.nb_clusters, opts)
        model.train()

    elif opts.mode == 'test':
        """
        Testing topoGAN
        """
        # Create directories if not exist.
        create_dirs_if_not_exist([opts.result_dir])
        
        # Simulate graph data for easy test the code
        source_target_domains = []
        for i in range(opts.num_domains):
          source_target_domains.append(np.random.normal(random.random(), random.random(), (30,595)))
        
        # Choose the source domain to be translated
        src_domain = 0
        
        # Load source and target TEST datasets
        tgt_loaders = []
        for domain in range(0, opts.num_domains):
            if domain == src_domain:
                source_feature = source_target_domains[domain]
                src_loader = get_loader(source_feature, opts.batch_size, opts.num_workers)
            else:
                target_feature = source_target_domains[domain]
                tgt_loader = get_loader(target_feature, opts.batch_size, opts.num_workers)
                tgt_loaders.append(tgt_loader)

        # Test TopoGAN
        model = TopoGAN(src_loader, tgt_loaders, opts.nb_clusters, opts)
        predicted_target_graphs, source_graphs = model.test()

        # Save data into csv files
        create_dirs_if_not_exist(['csv'])

        print("saving source graphs into csv file...") 
        f = source_graphs.cpu().numpy()
        dataframe = pd.DataFrame(data=f.astype(float))
        dataframe.to_csv('csv/source_graphs.csv', sep=' ', header=True, float_format='%.6f', index=False)

        print("saving predicted target graphs into csv files...") 
        for idx in range(len(predicted_target_graphs)): 
            f = predicted_target_graphs[idx].numpy()
            dataframe = pd.DataFrame(data=f.astype(float))
            dataframe.to_csv('csv/predicted_graphs_%d.csv'%(idx+1), sep=' ', header=True, float_format='%.6f', index=False)
        


import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
import argparse
import random
import numpy as np
import os
import tensorboardX
import itertools
import torch
import torch.optim as optim
from torchvision import datasets, transforms
from torch.utils.data import DataLoader, Subset
from model.GMVAE import GMVAE
import logging
import sys
sys.path.append('..')
from utils.draw import draw_grid



class GMVAE_runner():
    def __init__(self, args):
        self.args = args 

    def get_optimizer(self, parameters):
        if self.args.optimizer == 'Adam':
            return optim.Adam(parameters, lr=self.args.lr, weight_decay=self.args.weight_decay, betas=(0.5, 0.999))
        elif self.args.optimizer == 'RMSProp':
            return optim.RMSprop(parameters, lr=self.args.lr, weight_decay=self.args.weight_decay)
        elif self.args.optimizer == 'SGD':
            return optim.SGD(parameters, lr=self.args.lr, momentum=0.9)
        else:
            raise NotImplementedError('Optimizer {} not understood.'.format(self.args.optimizer))
    
    def train(self):
        model = GMVAE(v_dim = self.args.v_dim, h_dim = self.args.h_dim, w_dim = self.args.w_dim, \
            n_classes = self.args.n_classes)
        if self.args.gpu_list is not None:
            if len(self.args.gpu_list.split(',')) > 1:
                model = torch.nn.DataParallel(model).cuda()
            else:
                model = model.cuda()
        if isinstance(model, torch.nn.DataParallel):
            model = model.module
        optimizer = self.get_optimizer(model.parameters())

        if self.args.dataset == 'mnist':
            logging.info('loading mnist')
            dataset = datasets.MNIST(os.path.join(self.args.datapath, 'mnist'), download = True, train = True, \
                transform = transforms.ToTensor())
            num_items = len(dataset)
            indices = list(range(num_items))
            random_state = np.random.get_state()
            np.random.seed(2020)
            np.random.shuffle(indices)
            np.random.set_state(random_state)
            train_indices, test_indices = indices[:int(num_items * 0.8)], indices[int(num_items * 0.8):]
            testset = Subset(dataset, test_indices)
            trainset = Subset(dataset, train_indices)
        
        train_loader = DataLoader(trainset, batch_size = self.args.batch_size, shuffle = True, num_workers = 4)
        test_loader = DataLoader(testset, batch_size = self.args.batch_size, shuffle = True, num_workers = 4)
        test_iter = iter(test_loader)


        # self.args.log = self.args.run + time_string 
        tb_path = os.path.join(self.args.log, 'tensorboard')
        if os.path.exists(tb_path):
            shutil.rmtree(tb_path)
        tb_logger = tensorboardX.SummaryWriter(log_dir = tb_path)
        
        step = 0
        val_losses = []

        for epoch in range(self.args.n_epochs):
            for _,  (X, y) in  enumerate(train_loader):
                step += 1
                model.train()
                X = X.cuda()
                loss = model.ELBO(X)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

                if step % self.args.test_freq == 0:
                    test_X, _ = next(test_iter)
                    test_X = test_X.cuda()
                    model.eval()
                    test_loss = model.ELBO(test_X)
                    logging.info('loss: {}, test loss: {}'.format(loss.item(), test_loss.item()))

                    val_losses.append(test_loss.item())
                    tb_logger.add_scalar('loss', loss, global_step = step)
                    tb_logger.add_scalar('test_loss', test_loss, global_step = step)
                
                if step % self.args.draw_freq == 0:
                    self.test_cluster(model, step)
                
                if step % self.args.save_freq == 0:
                    ckpt_path = os.path.join(self.args.ckpt_dir, 'checkpoint{}k.pth'.format(step // 1000))
                    torch.save(model.state_dict(), ckpt_path)
                    logging.info('checkpoint{}k.pth saved!'.format(step // 1000))
                    

    def test_cluster(self, model, step):
        model.eval()
        N_sample = 10
        X_list = list()
        for c in range(self.args.n_classes):
            w_sample = torch.randn(N_sample, self.args.w_dim).cuda()
            h_sample, _ = model.P.gen_h(w_sample, c)
            X, _ = model.P.gen_v(h_sample)
            X_list.append(X.reshape(N_sample, 1, 28, 28))
        X_sample = torch.cat(X_list).cpu()
        draw_grid(X_sample, os.path.join(self.args.img_dir, 'grid{}.png'.format(step)))
        logging.info('grid{}.png saved!'.format(step))


    def test(self):
        pass
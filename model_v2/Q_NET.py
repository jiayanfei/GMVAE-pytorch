import numpy as np
import torch
from torch import nn, optim
from torch.nn import functional as F
import sys
sys.path.append('..')
from layers.base import MLP, convNet, fullconvNet


# Inference Network
class InferenceNet(nn.Module):
    # def __init__(self, v_dim, h_dim, w_dim, n_classes):
    def __init__(self, in_channel, image_size, h_dim, n_classes, M):
        super(InferenceNet, self).__init__()

        self.h_dim = h_dim
        self.M = M
        # self.v_dim = v_dim
        self.in_channel = in_channel
        self.image_size = image_size
        self.n_classes = n_classes
        
        hidden_size = 512
        nef = 16
        self.hidden_layer = convNet(in_channel, image_size, hidden_size)
        # Q(h|v)
        self.Qh_v_mean = nn.Linear(hidden_size, h_dim)
        self.Qh_v_logvar = nn.Linear(hidden_size, h_dim)
        # Q(w|v)

        self.Qc = nn.Sequential(
            nn.Linear(hidden_size + h_dim, n_classes),
            nn.Softmax(dim = -1)
        )
    
    def sample(self, mean, logstd):
        sample = mean + torch.randn_like(mean.expand(self.M, -1,-1)) * (logstd).exp()
        return sample
    
    def infer_c(self, v_feature, h_sample):
        # v_feature: [bs, hidden_size]  h_sample: [M, bs, h_dim]
        v_feature = v_feature.expand(self.M, -1, -1)
        concat = torch.cat([v_feature, h_sample], axis = -1)
        return self.Qc(concat) # [M, bs, n_classes]

    
    def forward(self, inputs):
        inputs = inputs.view(-1, self.in_channel, self.image_size, self.image_size)
        hidden_feature = self.hidden_layer(inputs)
        h_v_mean = self.Qh_v_mean(hidden_feature)
        h_v_logvar = self.Qh_v_logvar(hidden_feature)
        h_sample = self.sample(h_v_mean, h_v_logvar)
        c_vh = self.infer_c(hidden_feature, h_sample)
        return h_v_mean, h_v_logvar, h_sample, c_vh
    
    def predict(self, inputs):
        inputs = inputs.view(-1, self.in_channel, self.image_size, self.image_size)
        hidden_feature = self.hidden_layer(inputs)
        h_sample = self.Qh_v_mean(hidden_feature) # [M, h_dim]
        pred = self.Qc(torch.cat([hidden_feature, h_sample], axis = -1))
        return pred
    
    # def forward(self, X):
    #     h, *_ = self.infer_h(X)
    #     w, *_ = self.infer_w(X)
    #     return self.infer_c(w, h)
import sys
import os
import math

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.tensorboard import SummaryWriter
from tqdm import tqdm

sys.path.append(os.path.realpath(__file__ + '/../../'))

from data import cholec80_images
from models.MyViTMSN_pretraining import MyViTMSNModel_pretraining

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

class Config:

    # experiment directory
    exp_dir = os.path.join('exps', 'pretraining')

    # dataset info
    dataset_name = 'cholec80'
    data_root = os.path.join('cholec80')

    # metrics
    task_type = 'multi_class'
    monitor_metric = 'val_macro_f1'

    # optimization
    optimize_name = 'adamw'
    learning_rate = 1e-3
    weight_decay = 0.01
    lambda_val = 1

    # training
    num_epochs = 30
    batch_size = 200


def me_max_regularization(anchor: torch.Tensor):
    avg_anchor = torch.mean(anchor, dim=0)
    me_max_loss = - torch.sum(torch.log(avg_anchor**(-avg_anchor))) + math.log(float(len(avg_anchor)))
    return me_max_loss

def entropy_regularization(anchor: torch.Tensor):
    return torch.mean(torch.sum(torch.log(anchor**(-anchor)), dim=1))



def training_loop():

    datasets = cholec80_images.get_pytorch_dataloaders(
        data_root=Config.data_root,
        batch_size=Config.batch_size,
        double_img=True
    )

    model = MyViTMSNModel_pretraining(ipe=len(datasets['train']), num_epochs=Config.num_epochs, device=device)
    model.to(device)

    trainable_parameters = filter(lambda p: p.requires_grad, model.parameters())

    optimizer = optim.AdamW(trainable_parameters, lr=Config.learning_rate, weight_decay=Config.weight_decay)
    cross_entropy_criterion = nn.CrossEntropyLoss()
    writer = SummaryWriter(log_dir=os.path.join(Config.exp_dir, 'tb_logs'))

    for epoch in range(Config.num_epochs):

        '''Train loop'''
        running_train_loss = 0.0
        bar = tqdm(total=len(datasets['train']), desc=f'Train of epoch {epoch+1}', ncols=100)
        model.train()
        model.train_phase = True

        for i, (inputs_anchor, inputs_target, _) in enumerate(datasets['train'], 0):

            inputs_anchor, inputs_target = inputs_anchor.to(device), inputs_target.to(device)
            optimizer.zero_grad()

            output_anchor, output_target = model(inputs_anchor, inputs_target)

            loss_value = cross_entropy_criterion(output_anchor, output_target) + 5 * me_max_regularization(output_anchor) + entropy_regularization(output_anchor)
            running_train_loss += loss_value.detach()
            loss_value.backward()

            optimizer.step()
            model.exponential_moving_average()

            writer.add_scalar(f'TrainLoop/epoch_{epoch}_loss', loss_value.item(),i)
            bar.set_postfix(loss=f'{loss_value.item()}')
            bar.update(1)

        bar.close()
        epoch_train_loss = running_train_loss / len(datasets['train'])

        '''Saving model and info'''
        writer.add_scalar(f'Averaged losses for epoch/train', epoch_train_loss, epoch)
        torch.save(model.state_dict(), os.path.join(Config.exp_dir, 'checkpoints', f'model_{epoch}.pth'))
        filename = os.path.join(Config.exp_dir, 'checkpoints', 'models_details.txt')
        with open(filename, 'a') as file:
            concatenated_string = f'Epoch: {epoch} - Train loss: {epoch_train_loss}\n'
            file.write(concatenated_string)

    writer.flush()
    writer.close()


if __name__ == '__main__':
    training_loop()

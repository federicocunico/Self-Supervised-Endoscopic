import sys
import os

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.tensorboard import SummaryWriter
from torch.nn.functional import softmax
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
    learning_rate = 3e-1
    weight_decay = 0.01
    lambda_val = 1

    # training
    num_epochs = 10
    batch_size = 100
    validation_freq = 1


def training_loop():

    datasets = cholec80_images.get_pytorch_dataloaders(
        data_root=Config.data_root,
        batch_size=Config.batch_size
    )

    model = MyViTMSNModel_pretraining(device=device)
    model.to(device)

    optimizer = optim.Adam(model.parameters(), lr=Config.learning_rate, weight_decay=Config.weight_decay)
    cross_entropy_criterion = nn.CrossEntropyLoss()
    writer = SummaryWriter(log_dir=os.path.join(Config.exp_dir, 'tb_logs'))

    for epoch in range(Config.num_epochs):

        '''Train loop'''
        running_train_loss = 0.0
        bar = tqdm(total=len(datasets['train']), desc=f'Train of epoch {epoch+1}', ncols=100)
        model.train()

        for i, (inputs, _) in enumerate(datasets['train'], 0):

            inputs = inputs.to(device)
            optimizer.zero_grad()

            output_anchor, output_target = model(inputs, inputs)
            output_anchor, output_target = softmax(output_anchor, dim=1), softmax(output_target, dim=1)

            loss_value = cross_entropy_criterion(output_anchor, output_target) - Config.lambda_val * output_anchor.mean()
            running_train_loss += loss_value.detach()
            loss_value.backward()
            optimizer.step()

            writer.add_scalar(f'TrainLoop/epoch_{epoch}_loss', loss_value.detach(),i)
            bar.set_postfix(loss=loss_value.item())
            bar.update(1)

        bar.close()
        epoch_train_loss = running_train_loss / len(datasets['train'])


        ''' Validation loop'''
        running_validation_loss = 0.0
        bar = tqdm(total=len(datasets['validation']), desc=f'Train of epoch {epoch + 1}', ncols=100)
        model.eval()

        with torch.no_grad():
            for i, (inputs, _) in enumerate(datasets['validation'], 0):
                inputs = inputs.to(device)

                output_anchor, output_target = model(inputs, inputs)
                output_anchor, output_target = softmax(output_anchor, dim=1), softmax(output_target, dim=1)

                loss_value = cross_entropy_criterion(output_anchor, output_target)
                running_validation_loss += loss_value.item()

                writer.add_scalar(f'TestLoop/epoch_{epoch}_loss', loss_value.item(), i)
                bar.set_postfix(loss=loss_value.item())
                bar.update(1)

            bar.close()
            epoch_test_loss = running_validation_loss / len(datasets['validation'])

        writer.add_scalar(f'Averaged losses for epoch/train', epoch_train_loss, epoch)
        writer.add_scalar(f'Averaged losses for epoch/validation', epoch_test_loss, epoch)

        torch.save(model.state_dict(), os.path.join(Config.exp_dir, 'checkpoints', f'model_{epoch}.pth'))

        filename = os.path.join(Config.exp_dir, 'checkpoints', 'models_details.txt')
        with open(filename, 'a') as file:
            concatenated_string = f'Epoch: {epoch} - Train loss: {epoch_train_loss} - Validation loss: {epoch_test_loss}\n'
            file.write(concatenated_string)

    writer.flush()
    writer.close()

def test_loop(model_path: str):

    datasets = cholec80_images.get_pytorch_dataloaders(
        data_root=Config.data_root,
        batch_size=Config.batch_size,
        double_img=True
    )

    model = MyViTMSNModel_pretraining()
    model.load_state_dict(torch.load(model_path))
    model.to(device)
    model.eval()

    cross_entropy_criterion = nn.CrossEntropyLoss()
    writer = SummaryWriter(log_dir=os.path.join(Config.exp_dir, 'tb_logs'))

    running_test_loss = 0.0
    bar = tqdm(total=len(datasets['test']), desc=f'Test', ncols=100)

    for i, (inputs, _) in enumerate(datasets['test'], 0):
        inputs = inputs.to(device)

        output_anchor, output_target = model(inputs, inputs)
        output_anchor, output_target = softmax(output_anchor, dim=1), softmax(output_target, dim=1)

        loss_value = cross_entropy_criterion(output_anchor, output_target) - Config.lambda_val * output_anchor.mean()
        running_test_loss += loss_value.item()

        writer.add_scalar(f'TestLoop/loss', loss_value, i)
        bar.set_postfix(loss=loss_value.item())
        bar.update(1)

    bar.close()
    writer.add_scalar(f'TestLoop/FinalLoss', running_test_loss / len(datasets["test"]), 1)
    print(f'Average loss for test: {running_test_loss / len(datasets["test"])}')

    writer.flush()
    writer.close()


if __name__ == '__main__':
    training_loop()

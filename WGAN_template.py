from keras.layers import Input
from keras.models import Model
from keras.optimizers import Adam
import keras.backend as K

import numpy as np
import os

np.random.seed(1000)


def wasserstein_loss(y_true, y_pred):
    """
    Wasserstein distance for GAN
    author use:
    g_loss = mean(-fake_logit)
    c_loss = mean(fake_logit - true_logit)
    logit just denote result of discrimiantor without activated
    """
    return K.mean(y_true * y_pred)


def clip_weight(weight, lower, upper):
    weight_clip = []
    for w in weight:
        w = np.clip(w, lower, upper)
        weight_clip.append(w)
    return weight_clip


class WGAN:
    def __init__(self, dimensions, models, save_folders, dataset, clip=-1, optimizer='RMSprop'):
        self.dimensions = dimensions
        self.data_shape = dimensions['data_shape']
        self.latent_dim = dimensions['latent_dim']
        self.output_shape = dimensions['data_shape']
        self.save_folders = save_folders
        self.gray = dataset == 'mnist'
        self.epoch = 0
        self.clip = clip

        # Build and compile the discriminator
        self.discriminator = models['discriminator']
        self.discriminator.compile(loss=wasserstein_loss,
                                   optimizer=optimizer,
                                   metrics=['accuracy'])

        # Build the generator
        self.generator = models['generator']

        # The generator takes noise as input and generates imgs
        z = Input(shape=(dimensions['latent_dim'],))
        img = self.generator(z)

        # For the combined model we will only train the generator
        self.discriminator.trainable = False

        # The discriminator takes generated images as input and determines validity
        validity = self.discriminator(img)

        # The combined model  (stacked generator and discriminator)
        # Trains the generator to fool the discriminator
        self.combined = Model(z, validity)
        self.combined.compile(loss=wasserstein_loss,
                              optimizer=optimizer)

    def save_models(self):
        if not os.path.exists('Model_para'):
            os.mkdir('Model_para')
        self.generator.save('Model_para/models_wgan_generated_epoch_%d.h5' % self.epoch)
        self.discriminator.save('Model_para/models_wgan_discriminated_epoch_%d.h5' % self.epoch)

    def train(self, data_iterator, sample_results, save_models,
              epochs, batch_size=128,
              sample_interval=200, model_interval=500,
              gen_to_disc_ratio=1):

        # # Adversarial ground truths
        # valid = np.ones((batch_size, 1)) * -1
        # fake = np.ones((batch_size, 1))

        # Labels for generated and real data
        yDis = np.ones(2 * batch_size)

        # one-sided label smoothing
        yDis[:batch_size] = -1

        yGen = np.ones(batch_size) * -1

        data_iter = data_iterator(batch_size)

        for epoch in range(epochs):
            self.epoch = epoch

            # ---------------------
            #  Train Discriminator
            # ---------------------
            reps = max(1, int(1 / gen_to_disc_ratio))
            for _ in range(reps):
                # Select a random batch of images
                imgs = data_iter.__next__()

                noise = np.random.normal(0, 1, (batch_size, self.latent_dim))

                # Generate a batch of new images
                gen_imgs = self.generator.predict(noise)

                X = np.concatenate([imgs, gen_imgs])

                # Train the discriminator
                # d_loss_real = self.discriminator.train_on_batch(imgs, valid)
                # d_loss_fake = self.discriminator.train_on_batch(gen_imgs, fake)
                # d_loss = 0.5 * np.add(d_loss_real, d_loss_fake)
                d_loss = self.discriminator.train_on_batch(X, yDis)

                if self.clip != -1:
                    # clip weights of discriminator
                    d_weight = self.discriminator.get_weights()
                    d_weight = clip_weight(d_weight, -self.clip, self.clip)
                    self.discriminator.set_weights(d_weight)

            # ---------------------
            #  Train Generator
            # ---------------------

            reps = max(1, int(1 / gen_to_disc_ratio))
            for _ in range(reps):
                noise = np.random.normal(0, 1, (batch_size, self.latent_dim))

                # Train the generator (to have the discriminator label samples as valid)
                g_loss = self.combined.train_on_batch(noise, yGen)

                # Plot the progress
                print("%d [D loss: %f, acc.: %.2f%%] [G loss: %f]" % (epoch, d_loss[0], 100 * d_loss[1], g_loss))

            # If at save interval => save generated image samples
            if epoch % sample_interval == 0 and sample_results is not None:
                sample_results(epoch, self.generator, self.dimensions,
                               self.save_folders['results_folder'], self.gray)

            if epoch % model_interval == 0 and save_models is not None:
                save_models(self.generator, self.discriminator, self.save_folders['models_folder'], epoch)


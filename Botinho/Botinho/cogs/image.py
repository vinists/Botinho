import discord
from discord.ext import commands
from Services import dream_studio as ds, openai_client as oai
import logging


class Image(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="im", aliases=["imagem", "image"], description="IA geradora de imagens (Stable Diffusion)")
    async def imagem(self, ctx: commands.Context, *, content):
        """
            Utilização do gerador de imagens por IA:

            - Separe argumentos opcionais por ";"
            - Sempre coloque argumentos antes do prompt

            - Argumentos opcioanis:

            -- Número de imagens para retornar: -s

            -- CFG Scale (Classifier Free Guidance): -c | --cfg_scale
              - grau de liberdade do Modelo, quanto maior o valor, mais ao pé da letra será seguido o prompt.
              - Default = 7.0

            -- Imagem base (init_image): --img

            -- Sampler (use o google):
              - SAMPLER_DDIM = 0
              - SAMPLER_DDPM = 1
              - SAMPLER_K_EULER = 2
              - SAMPLER_K_EULER_ANCESTRAL = 3
              - SAMPLER_K_HEUN = 4
              - SAMPLER_K_DPM_2 = 5
              - SAMPLER_K_DPM_2_ANCESTRAL = 6
              - SAMPLER_K_LMS = 7 (Default)
              - SAMPLER_K_DPMPP_2S_ANCESTRAL = 8
              - SAMPLER_K_DPMPP_2M = 9


            Exemplo: !im -s 2; frog
        """
        try:
            await ctx.typing()

            ig = ds.ImageGenerator()
            prompt_data = ds.parse_arguments(content)

            if prompt_data.samples > 2 and not (await self.bot.is_owner(ctx.author)):
                return await ctx.send(f"{ctx.author.mention}, não consigo fazer mais que 2 imagens por solicitação...")

            attachments = ctx.message.attachments
            init_image = None

            if prompt_data.img is not None:
                init_image = ds.retrieve_image_from_url(prompt_data.img)
            elif len(attachments) > 0:
                init_image = ds.retrieve_image_from_url(str(ctx.message.attachments[0]))

            images = ig.generate_image(prompt_data, init_image)

            await ctx.send(content=ctx.author.mention, files=[discord.File(im["binary"], f"{im['seed']}.png") for im in images])

        except Exception as e:
            logging.error(e)
            await ctx.send(f"{ctx.author.mention}, não consegui gerar sua imagem...")

    @commands.command(name="im2")
    async def imagem_dalle(self, ctx: commands.Context, *, content):
        try:
            await ctx.typing()
            prompt_data = ds.parse_arguments(content)

            img = await oai.OpenAIGeneral.generate_image(prompt_data.prompt[0])
            embed = discord.Embed()
            embed.set_image(url=img)
            await ctx.send(content=ctx.author.mention, embed=embed)

        except Exception as e:
            logging.error(e)
            await ctx.send(f"{ctx.author.mention}, não consegui gerar sua imagem...")


async def setup(bot):
    await bot.add_cog(Image(bot))



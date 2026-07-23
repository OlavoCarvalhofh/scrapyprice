import scrapy


class ProductItem(scrapy.Item):
    url = scrapy.Field()
    loja = scrapy.Field()
    produto = scrapy.Field()
    sku = scrapy.Field()
    categoria = scrapy.Field()

    preco = scrapy.Field()
    preco_de = scrapy.Field()
    preco_a_vista = scrapy.Field()
    moeda = scrapy.Field()
    parcelas = scrapy.Field()
    parcela_valor = scrapy.Field()
    parcela_sem_juros = scrapy.Field()

    disponibilidade = scrapy.Field()
    vendedor = scrapy.Field()
    avaliacao_nota = scrapy.Field()
    avaliacao_qtd = scrapy.Field()
    imagem_url = scrapy.Field()

    fonte_extracao = scrapy.Field()

# python -m torch.distributed.run --nproc_per_node=16 train.py --cfg-path lavis/projects/blip2/train/caption_coco_ft.yaml
python train.py --cfg-path lavis/projects/blip2/train/caption_xai.yaml

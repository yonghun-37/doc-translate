"""Geometry for existing slide diffs; nested shapes use their outer group bounds."""
from pptx import Presentation


def shapes(path):
    prs = Presentation(path)
    result = {}
    def walk(items, slide, prefix='', group=None):
        for shape in items:
            name = prefix + shape.name
            boundary = group or shape
            result[(slide, name)] = {
                'x': boundary.left / prs.slide_width, 'y': boundary.top / prs.slide_height,
                'width': boundary.width / prs.slide_width, 'height': boundary.height / prs.slide_height}
            if hasattr(shape, 'shapes'):
                walk(shape.shapes, slide, name + ' / ', boundary)
    for i, slide in enumerate(prs.slides, 1):
        walk(slide.shapes, i)
    return result


def overlays(original, revised, changes):
    before, after = shapes(original), shapes(revised)
    result = []
    seen = set()
    for change in changes:
        if change['notes']:
            continue
        key = (change['slide'], change['shape'])
        sides = ['original'] if change['op'] == 'removed' else ['revised'] if change['op'] == 'added' else ['original', 'revised']
        for side in sides:
            rect = (before if side == 'original' else after).get(key)
            if not rect:
                continue
            identity = (side, key[0], tuple(rect.values()), change['op'])
            if identity not in seen:
                seen.add(identity)
                result.append({'slide': key[0], 'shape': key[1], 'side': side, 'op': change['op'], **rect})
    return result

# Copyright (c) 2021 PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import cv2
import numpy as np


class EvalAffine(object):
    def __init__(self, size, stride=64):
        super(EvalAffine, self).__init__()
        self.size = size
        self.stride = stride

    def __call__(self, image, im_info):
        s = self.size
        h, w, _ = image.shape
        trans, size_resized = get_affine_mat_kernel(h, w, s, inv=False)
        image_resized = cv2.warpAffine(image, trans, size_resized)
        return image_resized, im_info


def get_affine_mat_kernel(h, w, s, inv=False):
    if w < h:
        w_ = s
        h_ = int(np.ceil((s / w * h) / 64.) * 64)
        scale_w = w
        scale_h = h_ / w_ * w

    else:
        h_ = s
        w_ = int(np.ceil((s / h * w) / 64.) * 64)
        scale_h = h
        scale_w = w_ / h_ * h

    center = np.array([np.round(w / 2.), np.round(h / 2.)])

    size_resized = (w_, h_)
    trans = get_affine_transform(
        center, np.array([scale_w, scale_h]), 0, size_resized, inv=inv)

    return trans, size_resized


def get_affine_transform(center,
                         input_size,
                         rot,
                         output_size,
                         shift=(0., 0.),
                         inv=False):
    """Get the affine transform matrix, given the center/scale/rot/output_size.

    Args:
        center (np.ndarray[2, ]): Center of the bounding box (x, y).
        scale (np.ndarray[2, ]): Scale of the bounding box
            wrt [width, height].
        rot (float): Rotation angle (degree).
        output_size (np.ndarray[2, ]): Size of the destination heatmaps.
        shift (0-100%): Shift translation ratio wrt the width/height.
            Default (0., 0.).
        inv (bool): Option to inverse the affine transform direction.
            (inv=False: src->dst or inv=True: dst->src)

    Returns:
        np.ndarray: The transform matrix.
    """
    assert len(center) == 2
    assert len(input_size) == 2
    assert len(output_size) == 2
    assert len(shift) == 2

    scale_tmp = input_size

    shift = np.array(shift)
    src_w = scale_tmp[0]
    dst_w = output_size[0]
    dst_h = output_size[1]

    rot_rad = np.pi * rot / 180
    src_dir = rotate_point([0., src_w * -0.5], rot_rad)
    dst_dir = np.array([0., dst_w * -0.5])

    src = np.zeros((3, 2), dtype=np.float32)
    src[0, :] = center + scale_tmp * shift
    src[1, :] = center + src_dir + scale_tmp * shift
    src[2, :] = _get_3rd_point(src[0, :], src[1, :])

    dst = np.zeros((3, 2), dtype=np.float32)
    dst[0, :] = [dst_w * 0.5, dst_h * 0.5]
    dst[1, :] = np.array([dst_w * 0.5, dst_h * 0.5]) + dst_dir
    dst[2, :] = _get_3rd_point(dst[0, :], dst[1, :])

    if inv:
        trans = cv2.getAffineTransform(np.float32(dst), np.float32(src))
    else:
        trans = cv2.getAffineTransform(np.float32(src), np.float32(dst))

    return trans


def rotate_point(pt, angle_rad):
    """Rotate a point by an angle.

    Args:
        pt (list[float]): 2 dimensional point to be rotated
        angle_rad (float): rotation angle by radian

    Returns:
        list[float]: Rotated point.
    """
    assert len(pt) == 2
    sn, cs = np.sin(angle_rad), np.cos(angle_rad)
    new_x = pt[0] * cs - pt[1] * sn
    new_y = pt[0] * sn + pt[1] * cs
    rotated_pt = [new_x, new_y]

    return rotated_pt


def _get_3rd_point(a, b):
    """To calculate the affine matrix, three pairs of points are required. This
    function is used to get the 3rd point, given 2D points a & b.

    The 3rd point is defined by rotating vector `a - b` by 90 degrees
    anticlockwise, using b as the rotation center.

    Args:
        a (np.ndarray): point(x,y)
        b (np.ndarray): point(x,y)

    Returns:
        np.ndarray: The 3rd point.
    """
    assert len(a) == 2
    assert len(b) == 2
    direction = a - b
    third_pt = b + np.array([-direction[1], direction[0]], dtype=np.float32)

    return third_pt


class TopDownEvalAffine(object):
    """apply affine transform to image and coords

    Args:
        trainsize (list): [w, h], the standard size used to train
        records(dict): the dict contained the image and coords

    Returns:
        records (dict): contain the image and coords after tranformed

    """

    def __init__(self, trainsize):
        self.trainsize = trainsize

    def __call__(self, image, im_info):
        rot = 0
        imshape = im_info['im_shape'][::-1]
        center = im_info['center'] if 'center' in im_info else imshape / 2.
        scale = im_info['scale'] if 'scale' in im_info else imshape
        trans = get_affine_transform(center, scale, rot, self.trainsize)
        image = cv2.warpAffine(
            image,
            trans, (int(self.trainsize[0]), int(self.trainsize[1])),
            flags=cv2.INTER_LINEAR)

        return image, im_info

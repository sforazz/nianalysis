from nipype import config
config.enable_debug_mode()
from nianalysis.testing import BaseTestCase as TestCase  # @IgnorePep8 @Reimport
# from nianalysis.study.multimodal.test_motion_detection import (  # @IgnorePep8 @Reimport
#     MotionDetection, inputs)
from nianalysis.study.multimodal.mrpet import create_motion_correction_class  # @IgnorePep8 @Reimport


ref = 'ref'
ref_type = 't1'
t1s = ['ute']
t2s = ['t2']
epis = ['epi']
dmris = [['dwi_main', '0'], ['dwi_opposite', '-1']]


class TestMC(TestCase):

    def test_motion_correction(self):

        MotionCorrection, inputs, out_data = create_motion_correction_class(
            'MotionCorrection', ref, ref_type, t1s=t1s, t2s=t2s, dmris=dmris,
            epis=epis)

        study = self.create_study(
            MotionCorrection, 'MotionCorrection', inputs=inputs,
            enforce_inputs=False)
        study.data(out_data)
        self.assertDatasetCreated(out_data, study.name)

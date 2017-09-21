import logging  # @IgnorePep8
from nipype import config
config.enable_debug_mode()
from nianalysis.dataset import Dataset  # @IgnorePep8
from nianalysis.testing import BaseMultiSubjectTestCase as TestCase  # @IgnorePep8 @Reimport

from nianalysis.data_formats import zip_format, nifti_gz_format, text_matrix_format  # @IgnorePep8
from nianalysis.study.mri.structural.t2star import T2StarStudy  # @IgnorePep8

logger = logging.getLogger('NiAnalysis')


class TestQSM(TestCase):

#    def test_qsm_se_pipeline(self):
#        study = self.create_study(
#               T2StarStudy, 'qsm_se', input_datasets={
#               'coils': Dataset('swi_coils_se', zip_format)})
#        study.qsm_se_pipeline().run(work_dir=self.work_dir)
#        for fname in ('qsm.nii.gz', 'tissue_phase.nii.gz',
#                      'tissue_mask.nii.gz', 'qsm_mask.nii.gz'):
#            self.assertDatasetCreated(dataset_name=fname,
#                                      study_name=study.name)
            

#    def test_qsm_pipeline(self):
#       study = self.create_study(
#            T2StarStudy, 'qsm', input_datasets={
#                'coils': Dataset('swi_coils', zip_format)})    
#        study.qsm_pipeline().run(work_dir=self.work_dir)
#        for fname in ('qsm.nii.gz', 'tissue_phase.nii.gz',
#                      'tissue_mask.nii.gz', 'qsm_mask.nii.gz'):
#            self.assertDatasetCreated(dataset_name=fname,
#                                      study_name=study.name)        

    def test_ants_t2star(self):
        study = self.create_study(
            T2StarStudy, 'test_refined_mni', input_datasets={
                't1': Dataset('t1', nifti_gz_format),
                'raw_coils': Dataset('raw_coils', zip_format),
                'opti_betted_T2s': Dataset('opti_betted_t2s', nifti_gz_format),
                'opti_betted_T2s_mask': Dataset('opti_betted_T2s_mask', nifti_gz_format),
                'betted_T1_mask': Dataset('betted_T1_mask', nifti_gz_format),
                'betted_T1': Dataset('betted_T1', nifti_gz_format),
                'betted_T2s_mask': Dataset('betted_T2s_mask', nifti_gz_format),
                'betted_T2s': Dataset('betted_T2s', nifti_gz_format),
                #'t2s': Dataset('t2s', nifti_gz_format),
                'T2s_to_T1_mat': Dataset('T2s_to_T1_mat', text_matrix_format),
                'SUIT_to_T1_warp': Dataset('SUIT_to_T1_warp', nifti_gz_format),
                'T1_to_SUIT_warp': Dataset('T1_to_SUIT_warp', nifti_gz_format),
                'T1_to_SUIT_mat': Dataset('T1_to_SUIT_mat', text_matrix_format),
                'MNI_to_T1_warp': Dataset('MNI_to_T1_warp', nifti_gz_format),
                'T1_to_MNI_warp': Dataset('T1_to_MNI_warp', nifti_gz_format),
                'T1_to_MNI_mat': Dataset('T1_to_MNI_mat', text_matrix_format),
                'T2s_to_MNI_warp_refined': Dataset('T2s_to_MNI_warp_refined', nifti_gz_format),
                'MNI_to_T2s_warp_refined': Dataset('MNI_to_T2s_warp_refined', nifti_gz_format),
                'T2s_to_MNI_mat_refined': Dataset('T2s_to_MNI_mat_refined', text_matrix_format),
                'left_dentate_in_mni_refined': Dataset('left_dentate_in_mni_refined', nifti_gz_format, multiplicity='per_project'),
                'right_dentate_in_mni_refined': Dataset('right_dentate_in_mni_refined', nifti_gz_format, multiplicity='per_project'),
                'left_substantia_nigra_in_mni_refined': Dataset('left_substantia_nigra_in_mni_refined', nifti_gz_format, multiplicity='per_project'),
                'right_substantia_nigra_in_mni_refined': Dataset('right_substantia_nigra_in_mni_refined', nifti_gz_format, multiplicity='per_project'),
                'qsm': Dataset('qsm', nifti_gz_format)
                #'t2s_in_mni': Dataset('test_t2s_in_mni', nifti_gz_format),
                #'t2s_in_mni_initial_atlas': Dataset('test_t2s_mni_atlas', nifti_gz_format),
                #'T2s_to_MNI_Template_warp': Dataset('test_T2s_to_MNI_Template_warp', nifti_gz_format),
                #'T2s_to_MNI_Template_mat': Dataset('test_T2s_to_MNI_Template_mat', text_matrix_format),
                #'T2s_in_MNI_Template': Dataset('test_T2s_in_MNI_Template', nifti_gz_format),
                #'first_segm    entation_in_qsm': Dataset('test_first_segmentation_in_qsm', nifti_gz_format),
                #'right_dentate_in_qsm': Dataset('test_analysis_right_dentate_in_qsm', nifti_gz_format),
                #'left_dentate_in_qsm': Dataset('test_analysis_left_dentate_in_qsm', nifti_gz_format)
                })
        #study.t2s_atlas(qsm_num_channels=8, qsm_echo_times=[20], swi_coils_filename='T2swi3d_axial_p2_1.8mm_Coil').run(work_dir=self.work_dir, plugin='MultiProc')
        study.t2sLastEchoInMNI(study_name='TEST',qsm_num_channels=4, qsm_echo_times=[7.38, 22.14]).run(work_dir=self.work_dir, subject_ids=['frda'], visit_ids=['proc'], plugin='MultiProc')
        self.assertDatasetCreated(dataset_name='opti_betted_T1.nii.gz', study_name=study.name)
        #self.assertDatasetCreated(multiplicity='per_project',dataset_name='t2s_mni_atlas.nii.gz', study_name=study.name)
        
#    def test_ants(self):    
#        study = self.create_study(
#            T2StarStudy, 'optibet', input_datasets={
#                't2s': Dataset('t2s', nifti_gz_format),
#                't1': Dataset('t1', nifti_gz_format)})
#        study.ANTsRegistration().run(work_dir=self.work_dir,
#                                    plugin='MultiProc')
#        self.assertDatasetCreated('T2s2T1.nii.gz', study.name)
#        self.assertDatasetCreated('T2s2T1_mat.mat', study.name)
#        self.assertDatasetCreated('T12MNI_linear.nii.gz', study.name)
#        self.assertDatasetCreated('T12MNI_mat.mat', study.name)
#        self.assertDatasetCreated('T12MNI_warp.nii.gz', study.name)
#        self.assertDatasetCreated('T12MNI_invwarp.nii.gz', study.name)
       
#    def test_apply_trans(self):
#        study = self.create_study(
#            T2StarStudy, 'apply_tfm', input_datasets={
#                't1': Dataset('t1', nifti_gz_format),
#                't2s': Dataset('t2s', nifti_gz_format),
#                'qsm': Dataset('qsm', nifti_gz_format)})
#        study.applyTransform().run(work_dir=self.work_dir, plugin='Linear')
#        self.assertDatasetCreated('qsm_in_mni.nii.gz', study.name)
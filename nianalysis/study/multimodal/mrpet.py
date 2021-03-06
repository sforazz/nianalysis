from arcana.dataset import DatasetSpec, FieldSpec
from nianalysis.file_format import (
    nifti_gz_format, directory_format, text_format, png_format, dicom_format,
    text_matrix_format)
from nianalysis.interfaces.custom.motion_correction import (
    MeanDisplacementCalculation, MotionFraming, PlotMeanDisplacementRC,
    AffineMatAveraging, PetCorrectionFactor, CreateMocoSeries, FixedBinning,
    UmapAlign2Reference, ReorientUmap)
from nianalysis.citation import fsl_cite
from arcana.study.multi import (
    MultiStudy, SubStudySpec, MultiStudyMetaClass)
from nianalysis.study.mri.epi import EPIStudy
from nianalysis.study.mri.structural.t1 import T1Study
from nianalysis.study.mri.structural.t2 import T2Study
from nipype.interfaces.utility import Merge
from nianalysis.study.mri.structural.diffusion import DiffusionStudy
from nianalysis.requirement import fsl509_req, mrtrix3_req, ants2_req
from arcana.exception import ArcanaNameError
from arcana.dataset import DatasetMatch
import logging
from nianalysis.study.pet.base import PETStudy
from nianalysis.interfaces.custom.pet import (
    CheckPetMCInputs, PetImageMotionCorrection, StaticPETImageGeneration,
    PETFovCropping)
from arcana.parameter import ParameterSpec, SwitchSpec
import os
from nianalysis.interfaces.converters import Nii2Dicom
from arcana.interfaces.utils import CopyToDir, ListDir, dicom_fname_sort_key
from nipype.interfaces.fsl.preprocess import FLIRT
import nipype.interfaces.fsl as fsl
from nipype.interfaces.fsl.utils import ImageMaths
from nianalysis.interfaces.ants import AntsRegSyn
from nipype.interfaces.ants.resampling import ApplyTransforms


logger = logging.getLogger('Arcana')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

logging.getLogger("urllib3").setLevel(logging.WARNING)

reference_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../../',
                 'reference_data'))

template_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__).split('nianalysis')[0],
                 'nianalysis', 'nianalysis', 'templates'))


class MotionDetectionMixin(MultiStudy, metaclass=MultiStudyMetaClass):

    add_sub_study_specs = [
        SubStudySpec('pet_mc', PETStudy, {
            'pet_data_dir': 'pet_data_dir',
            'pet_data_reconstructed': 'pet_recon_dir',
            'pet_data_prepared': 'pet_recon_dir_prepared',
            'pet_start_time': 'pet_start_time',
            'pet_end_time': 'pet_end_time',
            'pet_duration': 'pet_duration'})]

    add_data_specs = [
        DatasetSpec('pet_data_dir', directory_format, optional=True),
        DatasetSpec('pet_data_reconstructed', directory_format, optional=True),
        DatasetSpec('struct2align', nifti_gz_format, optional=True),
        DatasetSpec('pet_data_prepared', directory_format,
                    'prepare_pet_pipeline'),
        DatasetSpec('static_motion_correction_results', directory_format,
                    'motion_correction_pipeline'),
        DatasetSpec('dynamic_motion_correction_results', directory_format,
                    'motion_correction_pipeline'),
        DatasetSpec('umap', dicom_format, optional=True),
        DatasetSpec('mean_displacement', text_format,
                    'mean_displacement_pipeline'),
        DatasetSpec('mean_displacement_rc', text_format,
                    'mean_displacement_pipeline'),
        DatasetSpec('mean_displacement_consecutive', text_format,
                    'mean_displacement_pipeline'),
        DatasetSpec('mats4average', text_format,
                    'mean_displacement_pipeline'),
        DatasetSpec('start_times', text_format,
                    'mean_displacement_pipeline'),
        DatasetSpec('motion_par_rc', text_format,
                    'mean_displacement_pipeline'),
        DatasetSpec('motion_par', text_format,
                    'mean_displacement_pipeline'),
        DatasetSpec('offset_indexes', text_format,
                    'mean_displacement_pipeline'),
        DatasetSpec('severe_motion_detection_report', text_format,
                    'mean_displacement_pipeline'),
        DatasetSpec('frame_start_times', text_format,
                    'motion_framing_pipeline'),
        DatasetSpec('frame_vol_numbers', text_format,
                    'motion_framing_pipeline'),
        DatasetSpec('timestamps', directory_format,
                    'motion_framing_pipeline'),
        DatasetSpec('mean_displacement_plot', png_format,
                    'plot_mean_displacement_pipeline'),
        DatasetSpec('rotation_plot', png_format,
                    'plot_mean_displacement_pipeline'),
        DatasetSpec('translation_plot', png_format,
                    'plot_mean_displacement_pipeline'),
        DatasetSpec('average_mats', directory_format,
                    'frame_mean_transformation_mats_pipeline'),
        DatasetSpec('correction_factors', text_format,
                    'pet_correction_factors_pipeline'),
        DatasetSpec('umaps_align2ref', directory_format,
                    'umap_realignment_pipeline'),
        DatasetSpec('umap_aligned_dicoms', directory_format,
                    'nifti2dcm_conversion_pipeline'),
        DatasetSpec('motion_detection_output', directory_format,
                    'gather_outputs_pipeline'),
        DatasetSpec('moco_series', directory_format,
                    'create_moco_series_pipeline'),
        DatasetSpec('fixed_binning_mats', directory_format,
                    'fixed_binning_pipeline'),
        FieldSpec('pet_duration', dtype=int,
                  pipeline_name='pet_header_info_extraction_pipeline'),
        FieldSpec('pet_end_time', dtype=str,
                  pipeline_name='pet_header_info_extraction_pipeline'),
        FieldSpec('pet_start_time', dtype=str,
                  pipeline_name='pet_header_info_extraction_pipeline')]

    add_parameter_specs = [
        ParameterSpec('framing_th', 2.0),
        ParameterSpec('framing_temporal_th', 30.0),
        ParameterSpec('framing_duration', 0),
        ParameterSpec('md_framing', True),
        ParameterSpec('align_pct', False),
        ParameterSpec('align_fixed_binning', False),
        ParameterSpec('moco_template', os.path.join(
            reference_path, 'moco_template.IMA')),
        ParameterSpec('PET_template_MNI', os.path.join(
            template_path, 'PET_template_MNI.nii.gz')),
        ParameterSpec('fixed_binning_n_frames', 0),
        ParameterSpec('pet_offset', 0),
        ParameterSpec('fixed_binning_bin_len', 60),
        ParameterSpec('crop_xmin', 100),
        ParameterSpec('crop_xsize', 130),
        ParameterSpec('crop_ymin', 100),
        ParameterSpec('crop_ysize', 130),
        ParameterSpec('crop_zmin', 20),
        ParameterSpec('crop_zsize', 100),
        ParameterSpec('PET2MNI_reg', False),
        ParameterSpec('dynamic_pet_mc', False)]

    def mean_displacement_pipeline(self, **kwargs):
        inputs = [DatasetSpec('ref_brain', nifti_gz_format)]
        sub_study_names = []
        input_names = []
        for sub_study_spec in self.sub_study_specs():
            try:
                inputs.append(
                    self.data_spec(sub_study_spec.inverse_map('motion_mats')))
                inputs.append(self.data_spec(sub_study_spec.inverse_map('tr')))
                inputs.append(
                    self.data_spec(sub_study_spec.inverse_map('start_time')))
                inputs.append(
                    self.data_spec(sub_study_spec.inverse_map(
                        'real_duration')))
                input_names.append(
                    self.spec(sub_study_spec.inverse_map(
                        'primary')).pattern)
                sub_study_names.append(sub_study_spec.name)
            except ArcanaNameError:
                continue  # Sub study doesn't have motion mat

        pipeline = self.create_pipeline(
            name='mean_displacement_calculation',
            inputs=inputs,
            outputs=[DatasetSpec('mean_displacement', text_format),
                     DatasetSpec('mean_displacement_rc', text_format),
                     DatasetSpec('mean_displacement_consecutive', text_format),
                     DatasetSpec('start_times', text_format),
                     DatasetSpec('motion_par_rc', text_format),
                     DatasetSpec('motion_par', text_format),
                     DatasetSpec('offset_indexes', text_format),
                     DatasetSpec('mats4average', text_format),
                     DatasetSpec('severe_motion_detection_report',
                                 text_format)],
            desc=("Calculate the mean displacement between each motion"
                  " matrix and a reference."),
            version=1,
            citations=[fsl_cite],
            **kwargs)

        num_motion_mats = len(sub_study_names)
        merge_motion_mats = pipeline.create_node(Merge(num_motion_mats),
                                                 name='merge_motion_mats')
        merge_tr = pipeline.create_node(Merge(num_motion_mats),
                                        name='merge_tr')
        merge_start_time = pipeline.create_node(Merge(num_motion_mats),
                                                name='merge_start_time')
        merge_real_duration = pipeline.create_node(Merge(num_motion_mats),
                                                   name='merge_real_duration')

        for i, sub_study_name in enumerate(sub_study_names, start=1):
            spec = self.sub_study_spec(sub_study_name)
            pipeline.connect_input(
                spec.inverse_map('motion_mats'), merge_motion_mats,
                'in{}'.format(i))
            pipeline.connect_input(
                spec.inverse_map('tr'), merge_tr,
                'in{}'.format(i))
            pipeline.connect_input(
                spec.inverse_map('start_time'), merge_start_time,
                'in{}'.format(i))
            pipeline.connect_input(
                spec.inverse_map('real_duration'), merge_real_duration,
                'in{}'.format(i))

        md = pipeline.create_node(MeanDisplacementCalculation(),
                                  name='scan_time_info')
        md.inputs.input_names = input_names
        pipeline.connect(merge_motion_mats, 'out', md, 'motion_mats')
        pipeline.connect(merge_tr, 'out', md, 'trs')
        pipeline.connect(merge_start_time, 'out', md, 'start_times')
        pipeline.connect(merge_real_duration, 'out', md, 'real_durations')
        pipeline.connect_input('ref_brain', md, 'reference')
        pipeline.connect_output('mean_displacement', md, 'mean_displacement')
        pipeline.connect_output(
            'mean_displacement_rc', md, 'mean_displacement_rc')
        pipeline.connect_output(
            'mean_displacement_consecutive', md,
            'mean_displacement_consecutive')
        pipeline.connect_output('start_times', md, 'start_times')
        pipeline.connect_output('motion_par_rc', md, 'motion_parameters_rc')
        pipeline.connect_output('motion_par', md, 'motion_parameters')
        pipeline.connect_output('offset_indexes', md, 'offset_indexes')
        pipeline.connect_output('mats4average', md, 'mats4average')
        pipeline.connect_output('severe_motion_detection_report', md,
                                'corrupted_volumes')
        return pipeline

    def motion_framing_pipeline(self, **kwargs):

        inputs = [DatasetSpec('mean_displacement', text_format),
                  DatasetSpec('mean_displacement_consecutive', text_format),
                  DatasetSpec('start_times', text_format)]
        if 'pet_data_dir' in self.input_names:
            inputs.append(FieldSpec('pet_start_time', str))
            inputs.append(FieldSpec('pet_end_time', str))
        pipeline = self.create_pipeline(
            name='motion_framing',
            inputs=inputs,
            outputs=[DatasetSpec('frame_start_times', text_format),
                     DatasetSpec('frame_vol_numbers', text_format),
                     DatasetSpec('timestamps', directory_format)],
            desc=("Calculate when the head movement exceeded a "
                  "predefined threshold (default 2mm)."),
            version=1,
            citations=[fsl_cite],
            **kwargs)

        framing = pipeline.create_node(MotionFraming(), name='motion_framing')
        framing.inputs.motion_threshold = self.parameter('framing_th')
        framing.inputs.temporal_threshold = self.parameter(
            'framing_temporal_th')
        framing.inputs.pet_offset = self.parameter('pet_offset')
        framing.inputs.pet_duration = self.parameter('framing_duration')
        pipeline.connect_input('mean_displacement', framing,
                               'mean_displacement')
        pipeline.connect_input('mean_displacement_consecutive', framing,
                               'mean_displacement_consec')
        pipeline.connect_input('start_times', framing, 'start_times')
        if 'pet_data_dir' in self.input_names:
            pipeline.connect_input('pet_start_time', framing, 'pet_start_time')
            pipeline.connect_input('pet_end_time', framing, 'pet_end_time')
        pipeline.connect_output('frame_start_times', framing,
                                'frame_start_times')
        pipeline.connect_output('frame_vol_numbers', framing,
                                'frame_vol_numbers')
        pipeline.connect_output('timestamps', framing, 'timestamps_dir')
        return pipeline

    def plot_mean_displacement_pipeline(self, **kwargs):

        pipeline = self.create_pipeline(
            name='plot_mean_displacement',
            inputs=[DatasetSpec('mean_displacement_rc', text_format),
                    DatasetSpec('motion_par_rc', text_format),
                    DatasetSpec('offset_indexes', text_format),
                    DatasetSpec('frame_start_times', text_format)],
            outputs=[DatasetSpec('mean_displacement_plot', png_format),
                     DatasetSpec('rotation_plot', png_format),
                     DatasetSpec('translation_plot', png_format)],
            desc=("Plot the mean displacement real clock"),
            version=1,
            citations=[fsl_cite],
            **kwargs)

        plot_md = pipeline.create_node(PlotMeanDisplacementRC(),
                                       name='plot_md')
        plot_md.inputs.framing = self.parameter('md_framing')
        pipeline.connect_input('mean_displacement_rc', plot_md,
                               'mean_disp_rc')
        pipeline.connect_input('offset_indexes', plot_md,
                               'false_indexes')
        pipeline.connect_input('frame_start_times', plot_md,
                               'frame_start_times')
        pipeline.connect_input('motion_par_rc', plot_md,
                               'motion_par_rc')
        pipeline.connect_output('mean_displacement_plot', plot_md,
                                'mean_disp_plot')
        pipeline.connect_output('rotation_plot', plot_md,
                                'rot_plot')
        pipeline.connect_output('translation_plot', plot_md,
                                'trans_plot')
        return pipeline

    def frame_mean_transformation_mats_pipeline(self, **kwargs):

        pipeline = self.create_pipeline(
            name='frame_mean_transformation_mats',
            inputs=[DatasetSpec('mats4average', text_format),
                    DatasetSpec('frame_vol_numbers', text_format)],
            outputs=[DatasetSpec('average_mats', directory_format)],
            desc=("Average all the transformation mats within each "
                  "detected frame."),
            version=1,
            citations=[fsl_cite],
            **kwargs)

        average = pipeline.create_node(AffineMatAveraging(),
                                       name='mats_averaging')
        pipeline.connect_input('frame_vol_numbers', average,
                               'frame_vol_numbers')
        pipeline.connect_input('mats4average', average,
                               'all_mats4average')
        pipeline.connect_output('average_mats', average,
                                'average_mats')
        return pipeline

    def fixed_binning_pipeline(self, **kwargs):

        pipeline = self.create_pipeline(
            name='fixed_binning',
            inputs=[DatasetSpec('start_times', text_format),
                    FieldSpec('pet_start_time', str),
                    FieldSpec('pet_duration', int),
                    DatasetSpec('mats4average', text_format)],
            outputs=[DatasetSpec('fixed_binning_mats', directory_format)],
            desc=("Pipeline to generate average motion matrices for "
                  "each bin in a dynamic PET reconstruction experiment."
                  "This will be the input for the dynamic motion correction."),
            version=1,
            citations=[fsl_cite], **kwargs)

        binning = pipeline.create_node(FixedBinning(), name='fixed_binning')
        pipeline.connect_input('start_times', binning, 'start_times')
        pipeline.connect_input('pet_start_time', binning, 'pet_start_time')
        pipeline.connect_input('pet_duration', binning, 'pet_duration')
        pipeline.connect_input('mats4average', binning, 'motion_mats')
        binning.inputs.n_frames = self.parameter('fixed_binning_n_frames')
        binning.inputs.pet_offset = self.parameter('pet_offset')
        binning.inputs.bin_len = self.parameter('fixed_binning_bin_len')

        pipeline.connect_output('fixed_binning_mats', binning,
                                'average_bin_mats')

        pipeline.assert_connected()
        return pipeline

    def pet_correction_factors_pipeline(self, **kwargs):

        pipeline = self.create_pipeline(
            name='pet_correction_factors',
            inputs=[DatasetSpec('timestamps', directory_format)],
            outputs=[DatasetSpec('correction_factors', text_format)],
            desc=("Pipeline to calculate the correction factors to "
                  "account for frame duration when averaging the PET "
                  "frames to create the static PET image"),
            version=1,
            citations=[fsl_cite],
            **kwargs)

        corr_factors = pipeline.create_node(PetCorrectionFactor(),
                                            name='pet_corr_factors')
        pipeline.connect_input('timestamps', corr_factors,
                               'timestamps')
        pipeline.connect_output('correction_factors', corr_factors,
                                'corr_factors')
        return pipeline

    def nifti2dcm_conversion_pipeline(self, **kwargs):

        pipeline = self.create_pipeline(
            name='conversion_to_dicom',
            inputs=[DatasetSpec('umaps_align2ref', directory_format),
                    DatasetSpec('umap', dicom_format)],
            outputs=[DatasetSpec('umap_aligned_dicoms', directory_format)],
            desc=(
                "Conversing aligned umap from nifti to dicom format - "
                "parallel implementation"),
            version=1,
            citations=(),
            **kwargs)

        list_niftis = pipeline.create_node(ListDir(), name='list_niftis')
        reorient_niftis = pipeline.create_node(
            ReorientUmap(), name='reorient_niftis', requirements=[mrtrix3_req])

        nii2dicom = pipeline.create_map_node(
            Nii2Dicom(), name='nii2dicom',
            iterfield=['in_file'], wall_time=20)
#         nii2dicom.inputs.extension = 'Frame'
        list_dicoms = pipeline.create_node(ListDir(), name='list_dicoms')
        list_dicoms.inputs.sort_key = dicom_fname_sort_key
        copy2dir = pipeline.create_node(CopyToDir(), name='copy2dir')
        copy2dir.inputs.extension = 'Frame'
        # Connect nodes
        pipeline.connect(list_niftis, 'files', reorient_niftis, 'niftis')
        pipeline.connect(reorient_niftis, 'reoriented_umaps', nii2dicom,
                         'in_file')
        pipeline.connect(list_dicoms, 'files', nii2dicom, 'reference_dicom')
        pipeline.connect(nii2dicom, 'out_file', copy2dir, 'in_files')
        # Connect inputs
        pipeline.connect_input('umaps_align2ref', list_niftis, 'directory')
        pipeline.connect_input('umap', list_dicoms, 'directory')
        pipeline.connect_input('umap', reorient_niftis, 'umap')
        # Connect outputs
        pipeline.connect_output('umap_aligned_dicoms', copy2dir, 'out_dir')

        return pipeline

    def umap_realignment_pipeline(self, **kwargs):
        inputs = [DatasetSpec('average_mats', directory_format),
                  DatasetSpec('umap_ref_coreg_matrix', text_matrix_format),
                  DatasetSpec('umap_ref_qform_mat', text_matrix_format)]
        outputs = []
        if ('umap_ref' in self.sub_study_names and
                'umap' in self.input_names):
            inputs.append(DatasetSpec('umap', nifti_gz_format))
            outputs.append(DatasetSpec('umaps_align2ref', directory_format))
        pipeline = self.create_pipeline(
            name='umap_realignment',
            inputs=inputs,
            outputs=outputs,
            desc=("Pipeline to align the original umap (if provided)"
                  "to match the head position in each frame and improve the "
                  "static PET image quality."),
            version=1,
            citations=[fsl_cite],
            **kwargs)
        frame_align = pipeline.create_node(
            UmapAlign2Reference(), name='umap2ref_alignment',
            requirements=[fsl509_req])
        frame_align.inputs.pct = self.parameter('align_pct')
        pipeline.connect_input('umap_ref_coreg_matrix', frame_align,
                               'ute_regmat')
        pipeline.connect_input('umap_ref_qform_mat', frame_align,
                               'ute_qform_mat')

        pipeline.connect_input('average_mats', frame_align, 'average_mats')
        pipeline.connect_input('umap', frame_align, 'umap')
        pipeline.connect_output('umaps_align2ref', frame_align,
                                'umaps_align2ref')
        return pipeline

    def create_moco_series_pipeline(self, **kwargs):
        """This pipeline is probably wrong as we still do not know how to
        import back the new moco series into the scanner. This was just a first
        attempt.
        """
        pipeline = self.create_pipeline(
            name='create_moco_series',
            inputs=[DatasetSpec('start_times', text_format),
                    DatasetSpec('motion_par', text_format)],
            outputs=[DatasetSpec('moco_series', directory_format)],
            desc=("Pipeline to generate a moco_series that can be then "
                  "imported back in the scanner and used to correct the"
                  " pet data"),
            version=1,
            citations=[fsl_cite],
            **kwargs)

        moco = pipeline.create_node(CreateMocoSeries(),
                                    name='create_moco_series')
        pipeline.connect_input('start_times', moco, 'start_times')
        pipeline.connect_input('motion_par', moco, 'motion_par')
        moco.inputs.moco_template = self.parameter('moco_template')

        pipeline.connect_output('moco_series', moco, 'modified_moco')
        return pipeline

    def gather_outputs_pipeline(self, **kwargs):
        inputs = [DatasetSpec('mean_displacement_plot', png_format),
                  DatasetSpec('motion_par', text_format),
                  DatasetSpec('correction_factors', text_format),
                  DatasetSpec('severe_motion_detection_report', text_format),
                  DatasetSpec('timestamps', directory_format)]
        if ('umap_ref' in self.sub_study_names and
                'umap' in self.input_names):
            inputs.append(DatasetSpec('umap_ref_preproc', nifti_gz_format))
            inputs.append(
                DatasetSpec('umap_aligned_dicoms', directory_format))

        pipeline = self.create_pipeline(
            name='gather_motion_detection_outputs',
            inputs=inputs,
            outputs=[DatasetSpec('motion_detection_output', directory_format)],
            desc=("Pipeline to gather together all the outputs from "
                  "the motion detection pipeline."),
            version=1,
            citations=[fsl_cite],
            **kwargs)

        merge_inputs = pipeline.create_node(Merge(len(inputs)),
                                            name='merge_inputs')
        for i, dataset in enumerate(inputs, start=1):
            pipeline.connect_input(
                dataset.name, merge_inputs, 'in{}'.format(i))

        copy2dir = pipeline.create_node(CopyToDir(), name='copy2dir')
        pipeline.connect(merge_inputs, 'out', copy2dir, 'in_files')

        pipeline.connect_output('motion_detection_output', copy2dir, 'out_dir')
        return pipeline

    prepare_pet_pipeline = MultiStudy.translate(
        'pet_mc', 'pet_data_preparation_pipeline')

    pet_header_info_extraction_pipeline = MultiStudy.translate(
        'pet_mc', 'pet_time_info_extraction_pipeline')

    def motion_correction_pipeline(self, **kwargs):
        inputs = [DatasetSpec('pet_data_prepared', directory_format),
                  DatasetSpec('ref_brain', nifti_gz_format),
                  DatasetSpec('mean_displacement_plot', png_format)]
        if self.parameter_spec('dynamic_pet_mc').value:
            inputs.append(DatasetSpec('fixed_binning_mats', directory_format))
            outputs = [DatasetSpec('dynamic_motion_correction_results',
                                   directory_format)]
            dynamic = True
        else:
            inputs.append(DatasetSpec('average_mats', directory_format))
            inputs.append(DatasetSpec('correction_factors', text_format))
            outputs = [DatasetSpec('static_motion_correction_results',
                                   directory_format)]
            dynamic = False
        if 'struct2align' in self.input_names:
            inputs.append(DatasetSpec('struct2align', nifti_gz_format))
            StructAlignment = True
        else:
            StructAlignment = False
        pipeline = self.create_pipeline(
            name='pet_mc',
            inputs=inputs,
            outputs=outputs,
            desc=("Given a folder with reconstructed PET data, this "
                  "pipeline will generate a motion corrected PET"
                  "image using information extracted from the MR-based "
                  "motion detection pipeline"),
            version=1,
            citations=[fsl_cite],
            **kwargs)
        check_pet = pipeline.create_node(
            CheckPetMCInputs(), requirements=[fsl509_req, mrtrix3_req],
            name='check_pet_data')
        pipeline.connect_input('pet_data_prepared', check_pet, 'pet_data')

        if StructAlignment:
            struct_reg = pipeline.create_node(
                FLIRT(), requirements=[fsl509_req], name='ref2structural_reg')
            pipeline.connect_input('ref_brain', struct_reg, 'reference')
            pipeline.connect_input('struct2align', struct_reg, 'in_file')
            struct_reg.inputs.dof = 6
            struct_reg.inputs.cost_func = 'normmi'
            struct_reg.inputs.cost = 'normmi'
        if dynamic:
            pipeline.connect_input('fixed_binning_mats', check_pet,
                                   'motion_mats')
        else:
            pipeline.connect_input('average_mats', check_pet,
                                   'motion_mats')
            pipeline.connect_input('correction_factors', check_pet,
                                   'corr_factors')
        pipeline.connect_input('ref_brain', check_pet,
                               'reference')
        if not dynamic:
            pet_mc = pipeline.create_map_node(
                PetImageMotionCorrection(), name='pet_mc',
                requirements=[fsl509_req],
                iterfield=['corr_factor', 'pet_image', 'motion_mat'])
            pipeline.connect(check_pet, 'corr_factors', pet_mc, 'corr_factor')
        else:
            pet_mc = pipeline.create_map_node(
                PetImageMotionCorrection(), name='pet_mc',
                requirements=[fsl509_req], iterfield=['pet_image',
                                                      'motion_mat'])
        pipeline.connect(check_pet, 'pet_images', pet_mc, 'pet_image')
        pipeline.connect(check_pet, 'motion_mats', pet_mc, 'motion_mat')
        pipeline.connect(check_pet, 'pet2ref_mat', pet_mc, 'pet2ref_mat')
        if StructAlignment:
            pipeline.connect(struct_reg, 'out_matrix_file', pet_mc,
                             'structural2ref_regmat')
            pipeline.connect_input('struct2align', pet_mc, 'structural_image')
        if self.parameter('PET2MNI_reg'):
            mni_reg = True
        else:
            mni_reg = False

        if dynamic:
            merge_mc = pipeline.create_node(fsl.Merge(), name='merge_pet_mc',
                                            requirements=[fsl509_req])
            merge_mc.inputs.dimension = 't'
            merge_no_mc = pipeline.create_node(
                fsl.Merge(), name='merge_pet_no_mc', requirements=[fsl509_req])
            merge_no_mc.inputs.dimension = 't'
            pipeline.connect(pet_mc, 'pet_mc_image', merge_mc, 'in_files')
            pipeline.connect(pet_mc, 'pet_no_mc_image', merge_no_mc,
                             'in_files')
        else:
            static_mc = pipeline.create_node(
                StaticPETImageGeneration(), name='static_mc_generation',
                requirements=[fsl509_req])
            pipeline.connect(pet_mc, 'pet_mc_image', static_mc,
                             'pet_mc_images')
            pipeline.connect(pet_mc, 'pet_no_mc_image', static_mc,
                             'pet_no_mc_images')
        merge_outputs = pipeline.create_node(Merge(3), name='merge_outputs')
        pipeline.connect_input('mean_displacement_plot', merge_outputs, 'in1')
        if not StructAlignment:
            cropping = pipeline.create_node(
                PETFovCropping(), name='pet_cropping')
            cropping.inputs.x_min = self.parameter('crop_xmin')
            cropping.inputs.x_size = self.parameter('crop_xsize')
            cropping.inputs.y_min = self.parameter('crop_ymin')
            cropping.inputs.y_size = self.parameter('crop_ysize')
            cropping.inputs.z_min = self.parameter('crop_zmin')
            cropping.inputs.z_size = self.parameter('crop_zsize')
            if dynamic:
                pipeline.connect(merge_mc, 'merged_file', cropping,
                                 'pet_image')
            else:
                pipeline.connect(static_mc, 'static_mc', cropping, 'pet_image')

            cropping_no_mc = pipeline.create_node(
                PETFovCropping(), name='pet_no_mc_cropping')
            cropping_no_mc.inputs.x_min = self.parameter('crop_xmin')
            cropping_no_mc.inputs.x_size = self.parameter('crop_xsize')
            cropping_no_mc.inputs.y_min = self.parameter('crop_ymin')
            cropping_no_mc.inputs.y_size = self.parameter('crop_ysize')
            cropping_no_mc.inputs.z_min = self.parameter('crop_zmin')
            cropping_no_mc.inputs.z_size = self.parameter('crop_zsize')
            if dynamic:
                pipeline.connect(merge_no_mc, 'merged_file', cropping_no_mc,
                                 'pet_image')
            else:
                pipeline.connect(static_mc, 'static_no_mc', cropping_no_mc,
                                 'pet_image')

            if mni_reg:
                if dynamic:
                    t_mean = pipeline.create_node(
                        ImageMaths(), requirements=[fsl509_req],
                        name='PET_temporal_mean')
                    t_mean.inputs.op_string = '-Tmean'
                    pipeline.connect(cropping, 'pet_cropped', t_mean,
                                     'in_file')
                reg_tmean2MNI = pipeline.create_node(
                    AntsRegSyn(num_dimensions=3, transformation='s',
                               out_prefix='reg2MNI', num_threads=4),
                    name='reg2MNI', wall_time=25,
                    requirements=[ants2_req])
                reg_tmean2MNI.inputs.ref_file = self.parameter(
                    'PET_template_MNI')
                if dynamic:
                    pipeline.connect(t_mean, 'out_file', reg_tmean2MNI,
                                     'input_file')

                    merge_trans = pipeline.create_node(
                        Merge(2), name='merge_transforms', wall_time=1)
                    pipeline.connect(reg_tmean2MNI, 'warp_file', merge_trans,
                                     'in1')
                    pipeline.connect(reg_tmean2MNI, 'regmat', merge_trans,
                                     'in2')
                    apply_trans = pipeline.create_node(
                        ApplyTransforms(), name='apply_trans', wall_time=7,
                        memory=24000, requirements=[ants2_req])
                    apply_trans.inputs.reference_image = self.parameter(
                        'PET_template_MNI')
                    apply_trans.inputs.interpolation = 'Linear'
                    apply_trans.inputs.input_image_type = 3
                    pipeline.connect(cropping, 'pet_cropped', apply_trans,
                                     'input_image')
                    pipeline.connect(merge_trans, 'out', apply_trans,
                                     'transforms')
                    pipeline.connect(apply_trans, 'output_image',
                                     merge_outputs, 'in2')
                else:
                    pipeline.connect(cropping, 'pet_cropped', reg_tmean2MNI,
                                     'input_file')
                    pipeline.connect(reg_tmean2MNI, 'reg_file',
                                     merge_outputs, 'in2')
            else:
                pipeline.connect(cropping, 'pet_cropped', merge_outputs, 'in2')
            pipeline.connect(cropping_no_mc, 'pet_cropped', merge_outputs,
                             'in3')
        else:
            if dynamic:
                pipeline.connect(merge_mc, 'merged_file', merge_outputs, 'in2')
                pipeline.connect(merge_no_mc, 'merged_file', merge_outputs,
                                 'in3')
            else:
                pipeline.connect(static_mc, 'static_mc', merge_outputs, 'in2')
                pipeline.connect(static_mc, 'static_no_mc', merge_outputs,
                                 'in3')
#         mcflirt = pipeline.create_node(MCFLIRT(), name='mcflirt')
#         pipeline.connect(merge_mc_ps, 'merged_file', mcflirt, 'in_file')
#         mcflirt.inputs.cost = 'normmi'

        copy2dir = pipeline.create_node(CopyToDir(), name='copy2dir')
        pipeline.connect(merge_outputs, 'out', copy2dir, 'in_files')
        if dynamic:
            pipeline.connect_output('dynamic_motion_correction_results',
                                    copy2dir, 'out_dir')
        else:
            pipeline.connect_output('static_motion_correction_results',
                                    copy2dir, 'out_dir')
        return pipeline


def create_motion_correction_class(name, ref=None, ref_type=None, t1s=None,
                                   t2s=None, dmris=None, epis=None,
                                   umap=None, dynamic=False, umap_ref=None,
                                   pet_data_dir=None, pet_recon_dir=None,
                                   struct2align=None):

    inputs = []
    dct = {}
    data_specs = []
    run_pipeline = False
    parameter_specs = [ParameterSpec('ref_preproc_resolution', [1])]
    switch_specs = []
    if struct2align is not None:
        struct_image = struct2align.split('/')[-1].split('.')[0]

    if pet_data_dir is not None:
        inputs.append(DatasetMatch('pet_data_dir', directory_format,
                                   'pet_data_dir'))
    if pet_recon_dir is not None:
        inputs.append(DatasetMatch('pet_data_reconstructed', directory_format,
                                   'pet_data_reconstructed'))
        if struct2align is not None:
            inputs.append(
                DatasetMatch('struct2align', nifti_gz_format, struct_image))
    if pet_data_dir is not None and pet_recon_dir is not None and dynamic:
        output_data = 'dynamic_motion_correction_results'
        parameter_specs.append(ParameterSpec('dynamic_pet_mc', True))
        if struct2align is not None:
            inputs.append(
                DatasetMatch('struct2align', nifti_gz_format, struct_image))
    elif (pet_recon_dir is not None and not dynamic):
        output_data = 'static_motion_correction_results'
    else:
        output_data = 'motion_detection_output'

    if not ref:
        raise Exception('A reference image must be provided!')
    if ref_type == 't1':
        ref_study = T1Study
    elif ref_type == 't2':
        ref_study = T2Study
    else:
        raise Exception('{} is not a recognized ref_type!The available '
                        'ref_types are t1 or t2.'.format(ref_type))

    study_specs = [SubStudySpec('ref', ref_study)]
    ref_spec = {'ref_brain': 'coreg_ref_brain'}
    inputs.append(DatasetMatch('ref_primary', dicom_format, ref))

    if umap_ref and umap:
        if umap_ref.endswith('/'):
            umap_ref = umap_ref.split('/')[-2]
        else:
            umap_ref = umap_ref.split('/')[-1]
        if umap_ref in t1s:
            umap_ref_study = T1Study
            t1s.remove(umap_ref)
        elif umap_ref in t2s:
            umap_ref_study = T2Study
            t2s.remove(umap_ref)
        else:
            umap_ref = None

    if t1s:
        study_specs.extend(
                [SubStudySpec('t1_{}'.format(i), T1Study,
                              ref_spec) for i in range(len(t1s))])
        inputs.extend(
            DatasetMatch('t1_{}_primary'.format(i), dicom_format, t1_scan)
            for i, t1_scan in enumerate(t1s))
        run_pipeline = True

    if t2s:
        study_specs.extend(
                [SubStudySpec('t2_{}'.format(i), T2Study,
                              ref_spec) for i in range(len(t2s))])
        inputs.extend(DatasetMatch('t2_{}_primary'.format(i), dicom_format,
                                   t2_scan)
                      for i, t2_scan in enumerate(t2s))
        run_pipeline = True

    if umap_ref and not umap:
        logger.info('Umap not provided. The umap realignment will not be '
                    'performed. Umap_ref will be trated as {}'
                    .format(umap_ref_study))

    elif umap_ref and umap:
        logger.info('Umap will be realigned to match the head position in '
                    'each frame.')
        if type(umap) == list and len(umap) > 1:
            logger.info('More than one umap provided. Only the first one will '
                        'be used.')
            umap = umap[0]
        study_specs.append(SubStudySpec('umap_ref', umap_ref_study, ref_spec))
        inputs.append(DatasetMatch('umap_ref_primary', dicom_format, umap_ref))
        inputs.append(DatasetMatch('umap', dicom_format, umap))

        run_pipeline = True

    elif not umap_ref and umap:
        logger.warning('Umap provided without corresponding reference image. '
                       'Realignment cannot be performed without umap_ref. Umap'
                       ' will be ignored.')

    if epis:
        epi_refspec = ref_spec.copy()
        epi_refspec.update({'ref_wm_seg': 'coreg_ref_wmseg',
                            'ref_preproc': 'coreg_ref_preproc'})
        study_specs.extend(SubStudySpec('epi_{}'.format(i), EPIStudy,
                                        epi_refspec)
                           for i in range(len(epis)))
        inputs.extend(
            DatasetMatch('epi_{}_primary'.format(i), dicom_format, epi_scan)
            for i, epi_scan in enumerate(epis))
        run_pipeline = True
    if dmris:
        unused_dwi = []
        dmris_main = [x for x in dmris if x[-1] == '0']
        dmris_ref = [x for x in dmris if x[-1] == '1']
        dmris_opposite = [x for x in dmris if x[-1] == '-1']
        dwi_refspec = ref_spec.copy()
        dwi_refspec.update({'ref_wm_seg': 'coreg_ref_wmseg',
                           'ref_preproc': 'coreg_ref_preproc'})
        if dmris_main:
            switch_specs.extend(
                SwitchSpec('dwi_{}_brain_extract_method'.format(i), 'fsl',
                           ('mrtrix', 'fsl')) for i in range(len(dmris_main)))
        if dmris_main and not dmris_opposite:
            logger.warning(
                'No opposite phase encoding direction b0 provided. DWI '
                'motion correction will be performed without distortion '
                'correction. THIS IS SUB-OPTIMAL!')
            study_specs.extend(
                SubStudySpec('dwi_{}'.format(i), DiffusionStudy, dwi_refspec)
                for i in range(len(dmris_main)))
            inputs.extend(
                DatasetMatch('dwi_{}_primary'.format(i), dicom_format,
                             dmris_main_scan[0])
                for i, dmris_main_scan in enumerate(dmris_main))
        if dmris_main and dmris_opposite:
            study_specs.extend(
                SubStudySpec('dwi_{}'.format(i), DiffusionStudy, dwi_refspec)
                for i in range(len(dmris_main)))
            inputs.extend(
                DatasetMatch('dwi_{}_primary'.format(i), dicom_format,
                             dmris_main[i][0]) for i in range(len(dmris_main)))
            if len(dmris_main) <= len(dmris_opposite):
                inputs.extend(DatasetMatch('dwi_{}_dwi_reference'.format(i),
                                           dicom_format, dmris_opposite[i][0])
                              for i in range(len(dmris_main)))
            else:
                inputs.extend(DatasetMatch('dwi_{}_dwi_reference'.format(i),
                                           dicom_format, dmris_opposite[0][0])
                              for i in range(len(dmris_main)))
        if dmris_opposite and dmris_main and not dmris_ref:
            study_specs.extend(
                SubStudySpec('b0_{}'.format(i), EPIStudy, dwi_refspec)
                for i in range(len(dmris_opposite)))
            inputs.extend(DatasetMatch('b0_{}_primary'.format(i),
                                       dicom_format, dmris_opposite[i][0])
                          for i in range(len(dmris_opposite)))
            if len(dmris_opposite) <= len(dmris_main):
                inputs.extend(DatasetMatch('b0_{}_reverse_phase'.format(i),
                                           dicom_format, dmris_main[i][0])
                              for i in range(len(dmris_opposite)))
            else:
                inputs.extend(DatasetMatch('b0_{}_reverse_phase'.format(i),
                                           dicom_format, dmris_main[0][0])
                              for i in range(len(dmris_opposite)))
        elif dmris_opposite and dmris_ref:
            min_index = min(len(dmris_opposite), len(dmris_ref))
            study_specs.extend(
                SubStudySpec('b0_{}'.format(i), EPIStudy, dwi_refspec)
                for i in range(min_index*2))
            inputs.extend(
                DatasetMatch('b0_{}_primary'.format(i), dicom_format,
                             scan[0])
                for i, scan in enumerate(dmris_opposite[:min_index] +
                                         dmris_ref[:min_index]))
            inputs.extend(
                DatasetMatch('b0_{}_reverse_phase'.format(i), dicom_format,
                             scan[0])
                for i, scan in enumerate(dmris_ref[:min_index] +
                                         dmris_opposite[:min_index]))
            unused_dwi = [scan for scan in dmris_ref[min_index:] +
                          dmris_opposite[min_index:]]
        elif dmris_opposite or dmris_ref:
            unused_dwi = [scan for scan in dmris_ref + dmris_opposite]
        if unused_dwi:
            logger.info(
                'The following scans:\n{}\nwere not assigned during the DWI '
                'motion detection initialization (probably a different number '
                'of main DWI scans and b0 images was provided). They will be '
                'processed os "other" scans.'
                .format('\n'.join(s[0] for s in unused_dwi)))
            study_specs.extend(
                SubStudySpec('t2_{}'.format(i), T2Study, ref_spec)
                for i in range(len(t2s), len(t2s)+len(unused_dwi)))
            inputs.extend(
                DatasetMatch('t2_{}_primary'.format(i), dicom_format, scan[0])
                for i, scan in enumerate(unused_dwi, start=len(t2s)))
        run_pipeline = True

    if not run_pipeline:
        raise Exception('At least one scan, other than the reference, must be '
                        'provided!')

    dct['add_sub_study_specs'] = study_specs
    dct['add_data_specs'] = data_specs
    dct['__metaclass__'] = MultiStudyMetaClass
    dct['add_parameter_specs'] = parameter_specs
    dct['add_switch_specs'] = switch_specs
    return (MultiStudyMetaClass(name, (MotionDetectionMixin,), dct), inputs,
            output_data)


def create_motion_detection_class(name, ref=None, ref_type=None, t1s=None,
                                  t2s=None, dmris=None, epis=None,
                                  pet_data_dir=None):

    inputs = []
    dct = {}
    data_specs = []
    run_pipeline = False
    parameter_specs = [ParameterSpec('ref_preproc_resolution', [1])]

    if pet_data_dir is not None:
        inputs.append(DatasetMatch('pet_data_dir', directory_format,
                                   'pet_data_dir'))

    if not ref:
        raise Exception('A reference image must be provided!')
    if ref_type == 't1':
        ref_study = T1Study
    elif ref_type == 't2':
        ref_study = T2Study
    else:
        raise Exception('{} is not a recognized ref_type!The available '
                        'ref_types are t1 or t2.'.format(ref_type))

    study_specs = [SubStudySpec('ref', ref_study)]
    ref_spec = {'ref_brain': 'coreg_ref_brain'}
    inputs.append(DatasetMatch('ref_primary', dicom_format, ref))

    if t1s:
        study_specs.extend(
                [SubStudySpec('t1_{}'.format(i), T1Study,
                              ref_spec) for i in range(len(t1s))])
        inputs.extend(
            DatasetMatch('t1_{}_primary'.format(i), dicom_format, t1_scan)
            for i, t1_scan in enumerate(t1s))
        run_pipeline = True

    if t2s:
        study_specs.extend(
                [SubStudySpec('t2_{}'.format(i), T2Study,
                              ref_spec) for i in range(len(t2s))])
        inputs.extend(DatasetMatch('t2_{}_primary'.format(i), dicom_format,
                                   t2_scan)
                      for i, t2_scan in enumerate(t2s))
        run_pipeline = True

    if epis:
        epi_refspec = ref_spec.copy()
        epi_refspec.update({'ref_wm_seg': 'coreg_ref_wmseg',
                            'ref_preproc': 'coreg_ref_preproc'})
        study_specs.extend(SubStudySpec('epi_{}'.format(i), EPIStudy,
                                        epi_refspec)
                           for i in range(len(epis)))
        inputs.extend(
            DatasetMatch('epi_{}_primary'.format(i), dicom_format, epi_scan)
            for i, epi_scan in enumerate(epis))
        run_pipeline = True
    if dmris:
        unused_dwi = []
        dmris_main = [x for x in dmris if x[-1] == '0']
        dmris_ref = [x for x in dmris if x[-1] == '1']
        dmris_opposite = [x for x in dmris if x[-1] == '-1']
        b0_refspec = ref_spec.copy()
        b0_refspec.update({'ref_wm_seg': 'coreg_ref_wmseg',
                           'ref_preproc': 'coreg_ref_preproc'})
        if dmris_main and not dmris_opposite:
            logger.warning(
                'No opposite phase encoding direction b0 provided. DWI '
                'motion correction will be performed without distortion '
                'correction. THIS IS SUB-OPTIMAL!')
            study_specs.extend(
                SubStudySpec('dwi_{}'.format(i), DiffusionStudy, ref_spec)
                for i in range(len(dmris_main)))
            inputs.extend(
                DatasetMatch('dwi_{}_primary'.format(i), dicom_format,
                             dmris_main_scan[0])
                for i, dmris_main_scan in enumerate(dmris_main))
        if dmris_main and dmris_opposite:
            study_specs.extend(
                SubStudySpec('dwi_{}'.format(i), DiffusionStudy, ref_spec)
                for i in range(len(dmris_main)))
            inputs.extend(
                DatasetMatch('dwi_{}_primary'.format(i), dicom_format,
                             dmris_main[i][0]) for i in range(len(dmris_main)))
            if len(dmris_main) <= len(dmris_opposite):
                inputs.extend(DatasetMatch('dwi_{}_dwi_reference'.format(i),
                                           dicom_format, dmris_opposite[i][0])
                              for i in range(len(dmris_main)))
            else:
                inputs.extend(DatasetMatch('dwi_{}_dwi_reference'.format(i),
                                           dicom_format, dmris_opposite[0][0])
                              for i in range(len(dmris_main)))
        if dmris_opposite and dmris_main and not dmris_ref:
            study_specs.extend(
                SubStudySpec('b0_{}'.format(i), EPIStudy, b0_refspec)
                for i in range(len(dmris_opposite)))
            inputs.extend(DatasetMatch('b0_{}_primary'.format(i),
                                       dicom_format, dmris_opposite[i][0])
                          for i in range(len(dmris_opposite)))
            if len(dmris_opposite) <= len(dmris_main):
                inputs.extend(DatasetMatch('b0_{}_reverse_phase'.format(i),
                                           dicom_format, dmris_main[i][0])
                              for i in range(len(dmris_opposite)))
            else:
                inputs.extend(DatasetMatch('b0_{}_reverse_phase'.format(i),
                                           dicom_format, dmris_main[0][0])
                              for i in range(len(dmris_opposite)))
        elif dmris_opposite and dmris_ref:
            min_index = min(len(dmris_opposite), len(dmris_ref))
            study_specs.extend(
                SubStudySpec('b0_{}'.format(i), EPIStudy, b0_refspec)
                for i in range(min_index*2))
            inputs.extend(
                DatasetMatch('b0_{}_primary'.format(i), dicom_format,
                             scan[0])
                for i, scan in enumerate(dmris_opposite[:min_index] +
                                         dmris_ref[:min_index]))
            inputs.extend(
                DatasetMatch('b0_{}_reverse_phase'.format(i), dicom_format,
                             scan[0])
                for i, scan in enumerate(dmris_ref[:min_index] +
                                         dmris_opposite[:min_index]))
            unused_dwi = [scan for scan in dmris_ref[min_index:] +
                          dmris_opposite[min_index:]]
        elif dmris_opposite or dmris_ref:
            unused_dwi = [scan for scan in dmris_ref + dmris_opposite]
        if unused_dwi:
            logger.info(
                'The following scans:\n{}\nwere not assigned during the DWI '
                'motion detection initialization (probably a different number '
                'of main DWI scans and b0 images was provided). They will be '
                'processed os "other" scans.'
                .format('\n'.join(s[0] for s in unused_dwi)))
            study_specs.extend(
                SubStudySpec('t2_{}'.format(i), T2Study, ref_spec)
                for i in range(len(t2s), len(t2s)+len(unused_dwi)))
            inputs.extend(
                DatasetMatch('t2_{}_primary'.format(i), dicom_format, scan[0])
                for i, scan in enumerate(unused_dwi, start=len(t2s)))
        run_pipeline = True

    if not run_pipeline:
        raise Exception('At least one scan, other than the reference, must be '
                        'provided!')

    dct['add_sub_study_specs'] = study_specs
    dct['add_data_specs'] = data_specs
    dct['__metaclass__'] = MultiStudyMetaClass
    dct['add_parameter_specs'] = parameter_specs
    return MultiStudyMetaClass(name, (MotionDetectionMixin,), dct), inputs

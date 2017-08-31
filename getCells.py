from __future__ import print_function
import numpy as np
import h5py
from skimage import io, filters, measure, segmentation, exposure
from skimage.filters import rank
from skimage.morphology import watershed, disk, reconstruction, remove_small_objects
from sklearn.cluster import k_means
import glob
from scipy import ndimage as ndi
import time

def resizeArray(arr):
    """
    Interpolate array to fit (200,200).
    """

    outArr = np.zeros((200,200))

    # Resize the arr
    ratio = 200.0/np.amax(arr.shape)

    arr = ndi.interpolation.zoom(arr, (ratio))
    outArr[:arr.shape[0],:arr.shape[1]] = arr
    return normalise(outArr), ratio

def normalise(inData):
    """
    Normalise array.
    """
    inDataAbs = np.fabs(inData)
    inDataMax = np.amax(inData)
    normalisedData = inDataAbs/inDataMax
    return normalisedData

if __name__ == "__main__":
    filepath = "/data/jim/alex/VAC/UCH.48h.REF.plateA.n1_AM/" # Filepath to plate images
    cellImages = []
    cellRatios = []
    cellSlide =[]
    t0 = time.time()

    redimgs = sorted(glob.glob(filepath+"*Red -*"))
    uvimgs = sorted(glob.glob(filepath+"*UV -*"))
    for i in np.arange(len(redimgs)):
        t1 = time.time()
        print("Markers from", uvimgs[i], "Cells from", redimgs[i])

        u = io.imread(uvimgs[i])
        thresh = filters.threshold_li(u)
        mask = u <= thresh
        labeled = measure.label(mask, background=1)
        markers = rank.median(labeled, disk(25))

        r = io.imread(redimgs[i])
        p0, p1 = np.percentile(r, (10, 70)) # These parameters can be changed to affect the sensitivity of measurement
        rRescaled = exposure.rescale_intensity(r, in_range=(p0, p1))
        thresh = filters.threshold_li(rRescaled)
        mask = rRescaled <= thresh
        gradient = rank.gradient(mask==0, disk(2))

        labeled = segmentation.watershed(gradient, markers)
        labeled = segmentation.clear_border(labeled) # Get rid of border cells

        cells = filter(None, ndi.find_objects(labeled)) # Get rid of all that "None" cruft

        print("Cells found:", len(cells))
        if len(cells) != 0:
            for j in np.arange(len(cells)):
                # Append cells to master list
                cellIm, cellRat = resizeArray(r[cells[j]])
                cellImages.append(cellIm)
                cellRatios.append(cellRat)
                cellSlide.append(i)
        t2 = time.time()
        print(t2-t1, "seconds")

    cellRatios = np.array(cellRatios)
    cellImages = np.array(cellImages)
    cellSlide = np.array(cellSlide)

    print("Running k-means cluster to filter out noise...")
    X_kmeans = k_means(np.reshape(cellImages,[-1,200*200]), 2, n_init=50) ## This looks like it works!!
    unique, counts = np.unique(X_kmeans[1], return_counts=True)
    print(dict(zip(unique, counts)))
    blueCells = np.argmax(counts) # This is where the cells are likely to be
    yellowCells = np.argmin(counts) # This is where the noise is likely to be
    blueMask = np.reshape(X_kmeans[1] == blueCells, cellImages.shape[:1])
    yellowMask = np.reshape(X_kmeans[1] == yellowCells, cellImages.shape[:1])
    cellImages = cellImages[blueMask] # Remove noise
    cellRatios = cellRatios[blueMask] # Remove noise
    cellSlide = cellSlide[blueMask] # Remove noise

    print(t2-t0, "s total time")
    h5f = h5py.File("./data/cellImages.h5", "w")
    h5f.create_dataset("cellImages", data=cellImages)
    h5f.create_dataset("cellRatios", data=cellRatios)
    h5f.close()

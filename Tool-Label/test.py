import matplotlib.pyplot as plt
import matplotlib.image as mpimg

# Load the image
image = mpimg.imread('./static/unlable_image/image1.jpg')

# Points to connect
points = [[0, 0], [100, 125], [45, 78], [90, 12]]

# Unzip the list of points into two separate lists: x and y coordinates
x, y = zip(*points)

# Display the image
plt.imshow(image)

# Plot the points and connect them on top of the image
plt.plot(x, y, marker='o', linestyle='-', color='r', linewidth=2)

# Optionally, adjust the axes for a better fit
plt.axis('on')  # Show the axes if you need to see the coordinates
plt.show()
